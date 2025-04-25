from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, URL
from flask_migrate import Migrate
import uuid
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from config import get_config
from utils.scraper import scrape_website, validate_url
from utils.search import search_serpapi, deduplicate_results
from utils.workflow import WorkflowManager
from models import db, Job, Theme
from tasks import celery, process_workflow_task, continue_workflow_after_selection_task
from prompts import (
    BRAND_BRIEF_PROMPT,
    SEARCH_ANALYSIS_PROMPT,
    CONTENT_ANALYST_PROMPT,
    CONTENT_STRATEGIST_CLUSTER_PROMPT,
    CONTENT_WRITER_PROMPT,
    CONTENT_EDITOR_PROMPT
)
from sqlalchemy import text

# Load environment variables
load_dotenv()

app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Initialize the configuration with the app
config.init_app(app)

# Log database configuration
app.logger.info(f"Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

# Initialize Celery with Flask app
celery.conf.update(app.config)

# Initialize extensions
csrf = CSRFProtect(app)
db.init_app(app)
migrate = Migrate(app, db)

# Run migrations on startup
with app.app_context():
    try:
        from flask_migrate import upgrade
        upgrade()
        app.logger.info("Database migrations completed successfully")
    except Exception as e:
        app.logger.error(f"Error running migrations: {str(e)}")
        raise

# Register Celery with Flask app
app.extensions['celery'] = celery

# Forms
class ContentWorkflowForm(FlaskForm):
    website_url = StringField('Website URL', validators=[DataRequired(), URL()])
    keywords = TextAreaField('Search Keywords (one per line or comma-separated)', validators=[DataRequired()])

@app.route('/', methods=['GET', 'POST'])
def index():
    form = ContentWorkflowForm()
    
    # Debug information
    app.logger.info(f"Method: {request.method}")
    if request.method == 'POST':
        app.logger.info(f"Form data: {request.form}")
        app.logger.info(f"Form validation: {form.validate()}")
        if form.errors:
            app.logger.info(f"Form errors: {form.errors}")
    
    if form.validate_on_submit():
        app.logger.info("Form validated successfully")
        
        try:
            # Create a unique job ID
            job_id = str(uuid.uuid4())
            
            # Process keywords
            keywords_text = form.keywords.data
            keywords = [k.strip() for k in re.split(r'[,\n]', keywords_text) if k.strip()]
            
            if not keywords:
                flash("Please enter at least one valid keyword", "error")
                return render_template('index.html', form=form)
            
            website_url = form.website_url.data
            if not validate_url(website_url):
                flash("Please enter a valid URL including http:// or https://", "error")
                return render_template('index.html', form=form)
            
            # Create new job in database
            new_job = Job(
                id=job_id,
                status='initialized',
                website_url=website_url,
                keywords=keywords,
                current_phase='INITIALIZATION',
                progress=0,
                workflow_data={},
                messages=[{
                    'text': "Job initialized, preparing to process...",
                    'timestamp': datetime.utcnow().isoformat()
                }]
            )
            db.session.add(new_job)
            db.session.commit()
            
            app.logger.info(f"Created job {job_id}")
            
            # Redirect to processing page
            return redirect(url_for('process_job', job_id=job_id))
        except Exception as e:
            app.logger.error(f"Error creating job: {str(e)}")
            flash(f"An error occurred: {str(e)}", "error")
            return render_template('index.html', form=form)
    else:
        if request.method == 'POST':
            app.logger.info("Form validation failed")
            flash("Please correct the errors in the form", "error")
    
    return render_template('index.html', form=form)

@app.route('/process/<job_id>', methods=['GET'])
def process_job(job_id):
    job = Job.query.get_or_404(job_id)
    app.logger.info(f"Processing job {job_id}")
    
    # If this is the first time viewing the process page, start the job
    if job.status == 'initialized':
        job.status = 'processing'
        job.messages.append("Starting content research workflow...")
        db.session.commit()
        
        # Start processing in Celery
        process_workflow_task.delay(job_id)
    
    return render_template('processing.html', job_id=job_id, job=job.to_dict())

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the current status of a job"""
    try:
        # Get a fresh copy of the job to ensure we have the latest data
        db.session.expire_all()  # Expire all objects in the session
        job = Job.query.get_or_404(job_id)
        
        app.logger.info(f"Job status requested for {job_id}: {job.status}")
        app.logger.info(f"Current messages count: {len(job.messages) if job.messages else 0}")
        app.logger.info(f"Messages content: {job.messages}")
        
        # Ensure messages is always a list
        messages = job.messages if job.messages else []
        
        # Create response data
        response_data = {
            'id': job.id,
            'status': job.status,
            'progress': job.progress,
            'current_phase': job.current_phase,
            'messages': messages,
            'error': job.error,
            'themes': [theme.to_dict() for theme in job.themes] if job.themes else []
        }
        
        app.logger.info(f"Returning {len(messages)} messages")
        app.logger.info(f"Response data: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        app.logger.error(f"Error getting job status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/results/<job_id>', methods=['GET'])
def results(job_id):
    job = Job.query.get_or_404(job_id)
    
    if job.status != 'completed':
        return redirect(url_for('process_job', job_id=job_id))
    
    return render_template('results.html', job=job.to_dict())

@app.route('/api/theme-selection/<job_id>', methods=['POST'])
@csrf.exempt
def theme_selection(job_id):
    try:
        # Get a fresh copy of the job
        db.session.expire_all()  # Expire all objects in the session
        job = Job.query.get_or_404(job_id)
        
        # Check if job is already being processed or not in correct state
        if job.in_progress or job.status != 'awaiting_selection':
            app.logger.warning(f"Theme selection rejected: job {job_id} in_progress={job.in_progress}, status={job.status}")
            return jsonify({'error': 'Job is already being processed or not awaiting selection'}), 409
        
        # Check if we received valid JSON
        if not request.is_json:
            app.logger.error(f"Received non-JSON request: {request.data}")
            return jsonify({'error': 'Invalid request format, expected JSON'}), 400
            
        data = request.json
        theme_number = data.get('theme_number')
        
        app.logger.info(f"Received theme selection: {theme_number} for job {job_id}")
        
        if not theme_number or not theme_number.isdigit():
            return jsonify({'error': 'Invalid theme number'}), 400
        
        # Idempotency check: if a theme is already selected or job is not awaiting_selection, reject
        already_selected = Theme.query.filter_by(job_id=job_id, is_selected=True).first()
        if already_selected:
            app.logger.warning(f"Theme selection already made for job {job_id}")
            return jsonify({'error': 'Theme already selected'}), 409
        
        # Update job with selected theme and advance workflow
        workflow_manager = WorkflowManager()
        workflow_manager.load_state(job.workflow_data)
        
        # Find the selected theme
        theme_number = int(theme_number)
        themes = Theme.query.filter_by(job_id=job_id).all()
        
        if 1 <= theme_number <= len(themes):
            selected_theme = themes[theme_number-1]
            selected_theme.is_selected = True
            db.session.commit()
        else:
            app.logger.error(f"Theme number {theme_number} out of range")
            return jsonify({'error': 'Theme number out of range'}), 400
        
        # Process theme selection
        workflow_manager.process_theme_selection(theme_number, [theme.to_dict() for theme in themes])
        
        # Save updated workflow state
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        job.messages.append(f"Selected theme: {selected_theme.title}")
        job.status = 'processing'
        db.session.commit()
        
        # Continue workflow in Celery
        continue_workflow_after_selection_task.delay(job_id)
        
        return jsonify({
            'status': 'success',
            'message': 'Theme selected',
            'theme': selected_theme.to_dict()
        }), 200
    
    except Exception as e:
        app.logger.error(f"Error in theme selection: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

def process_workflow(job_id):
    """Process the content workflow for a job"""
    job = Job.query.get_or_404(job_id)
    
    try:
        # Step 1: Initialize workflow
        job.status = 'processing'
        job.progress = 0
        
        workflow_manager = WorkflowManager()
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        
        # Step 2: Scrape website
        job.messages.append(f"Retrieving content from {job.website_url}...")
        website_content = scrape_website(job.website_url)
        
        if website_content.startswith("Error"):
            job.status = 'error'
            job.error = website_content
            job.messages.append(website_content)
            return
        
        job.website_content_length = len(website_content)
        job.progress = 10
        job.messages.append(f"Retrieved {len(website_content)} characters of content")
        
        # Step 3: Search for keywords
        job.messages.append(f"Searching for keywords: {', '.join(job.keywords)}")
        all_search_results = []
        failed_keywords = []
        
        # Get API key from config
        serpapi_key = app.config.get('SERPAPI_API_KEY')
        
        for keyword in job.keywords:
            try:
                results = search_serpapi(keyword, serpapi_key)
                if results:
                    all_search_results.extend(results)
                else:
                    failed_keywords.append(keyword)
                    job.messages.append(f"No results found for keyword: {keyword}")
            except Exception as e:
                failed_keywords.append(keyword)
                job.messages.append(f"Error searching for '{keyword}': {str(e)}")
        
        # Deduplicate results
        unique_results = deduplicate_results(all_search_results)
        total_results = len(unique_results)
        
        if total_results == 0:
            job.status = 'error'
            job.error = "No search results were found for any keywords. Try different keywords."
            job.messages.append("No search results were found for any keywords. Try different keywords.")
            return
        
        job.search_results = unique_results
        job.search_results_count = total_results
        job.progress = 20
        job.messages.append(f"Found {total_results} unique search results after deduplication")
        
        # Step 4: Begin agent workflow
        job.messages.append("Starting content research workflow...")
        
        # Advance workflow to RESEARCH phase
        workflow_manager.advance_phase()  # To RESEARCH
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        
        # Research phase
        job.messages.append("RESEARCH PHASE: Analyzing website content and search results")
        from utils.agents import run_agent_with_openai
        
        user_message = f"""
        Website URL: {job.website_url}
        Website Content: {website_content}
        Keywords: {', '.join(job.keywords)}
        Search Results: {json.dumps(unique_results, indent=2)}
        """
        response = run_agent_with_openai(RESEARCH_AGENT_PROMPT, user_message)
        
        # Parse the results
        brand_brief = ""
        search_analysis = ""
        
        if "## Brand Brief" in response:
            parts = response.split("## Brand Brief", 1)
            if len(parts) > 1:
                remaining = parts[1]
                if "## Search Results Analysis" in remaining:
                    brand_parts = remaining.split("## Search Results Analysis", 1)
                    brand_brief = brand_parts[0].strip()
                    search_analysis = brand_parts[1].strip()
                else:
                    brand_brief = remaining.strip()
        
        job.brand_brief = brand_brief
        job.search_analysis = search_analysis
        job.progress = 40
        job.messages.append("Completed research phase with brand brief and search analysis")
        
        # Advance workflow to ANALYSIS phase
        workflow_manager.advance_phase()  # To ANALYSIS
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        
        # Analysis phase
        job.messages.append("ANALYSIS PHASE: Identifying content themes")
        
        user_message = f"""
        Brand Brief: {job.brand_brief}
        Search Analysis: {job.search_analysis}
        Website Content: {website_content}
        Keywords: {', '.join(job.keywords)}
        """
        response = run_agent_with_openai(CONTENT_ANALYST_PROMPT, user_message)
        
        # Parse the themes
        themes = []
        if "## Content Themes" in response:
            themes_text = response.split("## Content Themes", 1)[1].strip()
            
            import re
            pattern = r'(\d+)\.\s+\*\*(.*?)\*\*\s+(.*?)(?=\d+\.\s+\*\*|\Z)'
            matches = re.finditer(pattern, themes_text, re.DOTALL)
            
            for match in matches:
                theme_num = match.group(1).strip()
                title = match.group(2).strip()
                description = match.group(3).strip()
                
                themes.append({
                    "number": int(theme_num),
                    "title": title,
                    "description": description
                })
        
        job.content_themes = themes
        job.progress = 60
        job.messages.append(f"Identified {len(themes)} content themes")
        
        # Advance workflow to THEME_SELECTION phase
        workflow_manager.advance_phase()  # To THEME_SELECTION
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        
        # Wait for user to select a theme
        job.status = 'awaiting_selection'
        job.messages.append("Waiting for user to select a content theme")
        
    except Exception as e:
        job.status = 'error'
        job.error = str(e)
        job.messages.append(f"Error: {str(e)}")
        app.logger.error(f"Error processing job {job_id}: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())

def continue_workflow_after_selection(job_id):
    """Continue the workflow after theme selection"""
    job = Job.query.get_or_404(job_id)
    
    try:
        workflow_manager = WorkflowManager()
        workflow_manager.load_state(job.workflow_data)
        
        # Get the selected theme
        selected_theme = Theme.query.filter_by(job_id=job_id, is_selected=True).first()
        if not selected_theme:
            job.status = 'error'
            job.error = "No theme was selected"
            job.messages.append("Error: No theme was selected")
            return
        
        # Strategy phase
        job.messages.append("STRATEGY PHASE: Creating content cluster framework")
        
        from utils.agents import run_agent_with_openai
        
        user_message = f"""
        Selected Theme: {selected_theme.title}
        Theme Description: {selected_theme.description}
        Brand Brief: {job.brand_brief}
        Search Analysis: {job.search_analysis}
        """
        content_cluster = run_agent_with_openai(CONTENT_STRATEGIST_CLUSTER_PROMPT, user_message)
        
        job.content_cluster = content_cluster
        job.progress = 70
        job.messages.append("Completed content cluster framework")
        
        # Advance workflow to CONTENT_IDEATION phase
        workflow_manager.advance_phase()  # To CONTENT_IDEATION
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        
        # Content ideation phase
        job.messages.append("CONTENT IDEATION PHASE: Developing article ideas")
        
        user_message = f"""
        Content Cluster: {job.content_cluster}
        Selected Theme: {selected_theme.title}
        Theme Description: {selected_theme.description}
        Brand Brief: {job.brand_brief}
        """
        article_ideas = run_agent_with_openai(CONTENT_WRITER_PROMPT, user_message)
        
        job.article_ideas = article_ideas
        job.progress = 85
        job.messages.append("Developed article ideas for the content plan")
        
        # Advance workflow to EDITORIAL phase
        workflow_manager.advance_phase()  # To EDITORIAL
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        
        # Editorial phase
        job.messages.append("EDITORIAL PHASE: Refining the content plan")
        
        user_message = f"""
        Article Ideas: {job.article_ideas}
        Content Cluster: {job.content_cluster}
        Selected Theme: {selected_theme.title}
        Brand Brief: {job.brand_brief}
        """
        final_plan = run_agent_with_openai(CONTENT_EDITOR_PROMPT, user_message)
        
        job.final_plan = final_plan
        job.progress = 100
        
        # Complete the workflow
        workflow_manager.advance_phase()  # To COMPLETION
        job.workflow_data = workflow_manager.save_state()
        job.current_phase = workflow_manager.current_phase
        job.status = 'completed'
        job.completed_at = datetime.now().isoformat()
        job.messages.append("Workflow complete! Content plan is ready.")
        
    except Exception as e:
        job.status = 'error'
        job.error = str(e)
        job.messages.append(f"Error: {str(e)}")
        app.logger.error(f"Error in theme selection workflow: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())

@app.route('/admin/jobs')
def admin_jobs():
    # Get all jobs ordered by created_at descending
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('admin/jobs.html', jobs=jobs)

@app.route('/admin/jobs/cleanup', methods=['POST'])
def cleanup_jobs():
    try:
        # Start a transaction
        with db.session.begin():
            # First delete themes for incomplete jobs
            db.session.execute(
                text("""
                DELETE FROM themes 
                WHERE job_id IN (
                    SELECT id FROM jobs WHERE status != 'completed'
                )
                """)
            )
            
            # Get count of jobs to be deleted
            count = Job.query.filter(Job.status != 'completed').count()
            
            # Then delete the jobs
            db.session.execute(
                text("DELETE FROM jobs WHERE status != 'completed'")
            )
            
            # Commit the transaction
            db.session.commit()
            
        flash(f'Successfully deleted {count} incomplete jobs and their associated themes', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting jobs: {str(e)}', 'error')
    
    return redirect(url_for('admin_jobs'))

@app.route('/test-celery')
def test_celery():
    from celery_worker import celery
    from tasks import test_task
    
    # Send a test task
    result = test_task.delay()
    
    return {
        'task_id': result.id,
        'status': 'Task sent successfully'
    }

if __name__ == '__main__':
    app.run(debug=True) 
