"""
Flask Web Application for Procurement Intelligence Tool.
Provides dashboard and management interface for opportunities.
"""

import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db
from src.discovery import DiscoveryEngine, manual_add_article
from src.scoring import ScoringEngine, get_score_breakdown
from src.rfp_discovery import RFPDiscoveryEngine, manual_add_rfp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
app.secret_key = 'procurement-intel-secret-key-change-in-production'


# ============== Dashboard Routes ==============

@app.route('/')
def dashboard():
    """Main dashboard showing overview of opportunities."""
    stats = db.get_dashboard_stats()
    opportunities = db.get_all_opportunities()

    # Get top opportunities (highest heat scores)
    top_opportunities = sorted(opportunities, key=lambda x: x['heat_score'], reverse=True)[:10]

    # Get recent opportunities
    recent_opportunities = sorted(opportunities, key=lambda x: x['first_detected'] or '', reverse=True)[:10]

    return render_template('dashboard.html',
                         stats=stats,
                         top_opportunities=top_opportunities,
                         recent_opportunities=recent_opportunities)


@app.route('/opportunities')
def opportunities_list():
    """List all opportunities with filtering."""
    status_filter = request.args.get('status')
    min_score = request.args.get('min_score', type=float)
    sort_by = request.args.get('sort', 'heat_score')

    opportunities = db.get_all_opportunities(status=status_filter, min_heat_score=min_score)

    # Sort options
    if sort_by == 'heat_score':
        opportunities = sorted(opportunities, key=lambda x: x['heat_score'], reverse=True)
    elif sort_by == 'recent':
        opportunities = sorted(opportunities, key=lambda x: x['first_detected'] or '', reverse=True)
    elif sort_by == 'entity':
        opportunities = sorted(opportunities, key=lambda x: x['entity_name'])

    return render_template('opportunities.html',
                         opportunities=opportunities,
                         status_filter=status_filter,
                         min_score=min_score,
                         sort_by=sort_by)


@app.route('/opportunity/<int:opportunity_id>')
def opportunity_detail(opportunity_id):
    """Detailed view of a single opportunity."""
    opportunity = db.get_opportunity(opportunity_id)
    if not opportunity:
        flash('Opportunity not found', 'error')
        return redirect(url_for('opportunities_list'))

    articles = db.get_opportunity_articles(opportunity_id)
    activities = db.get_opportunity_activities(opportunity_id)
    entity = db.get_entity(opportunity['entity_id'])
    contacts = db.get_entity_contacts(opportunity['entity_id'])
    score_breakdown = get_score_breakdown(opportunity_id)

    return render_template('opportunity_detail.html',
                         opportunity=opportunity,
                         articles=articles,
                         activities=activities,
                         entity=entity,
                         contacts=contacts,
                         score_breakdown=score_breakdown)


@app.route('/opportunity/<int:opportunity_id>/update', methods=['POST'])
def update_opportunity(opportunity_id):
    """Update opportunity status, priority, or notes."""
    status = request.form.get('status')
    priority = request.form.get('priority')
    notes = request.form.get('notes')

    updates = {}
    if status:
        updates['status'] = status
    if priority:
        updates['priority'] = priority
    if notes is not None:
        updates['notes'] = notes

    if updates:
        db.update_opportunity(opportunity_id, **updates)

        # Log the activity
        if status:
            db.add_activity_log(opportunity_id, 'status_change', f'Status changed to {status}')
        if priority:
            db.add_activity_log(opportunity_id, 'priority_change', f'Priority changed to {priority}')
        if notes is not None:
            db.add_activity_log(opportunity_id, 'note_added', 'Notes updated')

        flash('Opportunity updated successfully', 'success')

    return redirect(url_for('opportunity_detail', opportunity_id=opportunity_id))


@app.route('/opportunity/<int:opportunity_id>/add_note', methods=['POST'])
def add_note(opportunity_id):
    """Add a note to an opportunity."""
    note = request.form.get('note')
    if note:
        opportunity = db.get_opportunity(opportunity_id)
        existing_notes = opportunity.get('notes') or ''
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_notes = f"{existing_notes}\n\n[{timestamp}]\n{note}".strip()

        db.update_opportunity(opportunity_id, notes=new_notes)
        db.add_activity_log(opportunity_id, 'note_added', f'Note added: {note[:50]}...')

        flash('Note added successfully', 'success')

    return redirect(url_for('opportunity_detail', opportunity_id=opportunity_id))


# ============== Discovery Routes ==============

@app.route('/discover')
def discover_page():
    """Discovery management page."""
    sources = db.get_all_sources()
    keywords = db.get_all_keywords()

    return render_template('discover.html', sources=sources, keywords=keywords)


@app.route('/discover/run', methods=['POST'])
def run_discovery():
    """Run a discovery cycle."""
    custom_queries = request.form.get('queries')
    comprehensive = request.form.get('comprehensive') == 'on'

    queries = None
    if custom_queries:
        queries = [q.strip() for q in custom_queries.split('\n') if q.strip()]
    elif comprehensive:
        queries = get_comprehensive_florida_queries()

    engine = DiscoveryEngine()
    results = engine.run_discovery(search_queries=queries)

    flash(f'Discovery complete. Found {len(results)} new opportunities.', 'success')
    return redirect(url_for('opportunities_list'))


def get_comprehensive_florida_queries():
    """Get comprehensive Florida-wide search queries."""
    queries = [
        # General statewide searches
        'Florida county procurement violation',
        'Florida school board bid rigging',
        'Florida county audit findings',
        'Florida city contract scandal',
        'Florida government corruption investigation',
        'Florida inspector general report',
        'Florida grand jury government',
        'Florida ethics commission violation',
        'Florida auditor general findings',
        'Florida municipal corruption',
        'Florida construction contract fraud',
        'Florida vendor kickback',
        'Florida no-bid contract controversy',
        'Florida FDLE investigation government',
        'Florida FBI public corruption',
        # South Florida
        'Miami-Dade County procurement scandal',
        'Broward County bid rigging',
        'Palm Beach County contract fraud',
        # Central Florida
        'Orange County Florida procurement scandal',
        'Orlando city contract investigation',
        # Tampa Bay
        'Hillsborough County procurement scandal',
        'Tampa city contract fraud',
        'Pinellas County audit findings',
        # Jacksonville
        'Duval County procurement scandal',
        'Jacksonville city contract fraud',
        # Other major counties
        'Lee County Florida procurement scandal',
        'Polk County Florida contract scandal',
        'Brevard County bid rigging',
        'Sarasota County corruption',
        'Collier County contract fraud',
        'Leon County procurement scandal',
        'Escambia County bid rigging',
        'Marion County procurement scandal',
        # School districts
        'Miami-Dade schools construction scandal',
        'Broward County schools bid rigging',
        'Hillsborough schools contract fraud',
        'Orange County schools procurement',
        'Palm Beach schools audit findings',
        'Marion County schools construction',
    ]
    return queries


@app.route('/discover/add_article', methods=['POST'])
def add_article():
    """Manually add an article URL for processing."""
    url = request.form.get('url')
    if not url:
        flash('Please provide a URL', 'error')
        return redirect(url_for('discover_page'))

    results = manual_add_article(url)

    if results:
        flash(f'Article processed. Found {len(results)} opportunities.', 'success')
        if len(results) == 1:
            return redirect(url_for('opportunity_detail', opportunity_id=results[0]['opportunity_id']))
    else:
        flash('No relevant procurement issues found in article.', 'warning')

    return redirect(url_for('discover_page'))


# ============== Entity Routes ==============

@app.route('/entities')
def entities_list():
    """List all tracked entities."""
    entities = db.get_all_entities()
    return render_template('entities.html', entities=entities)


@app.route('/entity/<int:entity_id>')
def entity_detail(entity_id):
    """View entity details and associated opportunities."""
    entity = db.get_entity(entity_id)
    if not entity:
        flash('Entity not found', 'error')
        return redirect(url_for('entities_list'))

    # Get opportunities for this entity
    all_opportunities = db.get_all_opportunities()
    entity_opportunities = [o for o in all_opportunities if o['entity_id'] == entity_id]

    contacts = db.get_entity_contacts(entity_id)

    return render_template('entity_detail.html',
                         entity=entity,
                         opportunities=entity_opportunities,
                         contacts=contacts)


@app.route('/entity/<int:entity_id>/add_contact', methods=['POST'])
def add_contact(entity_id):
    """Add a contact to an entity."""
    name = request.form.get('name')
    title = request.form.get('title')
    role = request.form.get('role')
    email = request.form.get('email')
    phone = request.form.get('phone')

    if not name:
        flash('Contact name is required', 'error')
        return redirect(url_for('entity_detail', entity_id=entity_id))

    db.create_contact(entity_id, name, title=title, role=role, email=email, phone=phone)
    flash('Contact added successfully', 'success')

    return redirect(url_for('entity_detail', entity_id=entity_id))


# ============== API Routes ==============

@app.route('/api/opportunities')
def api_opportunities():
    """API endpoint for opportunities."""
    status = request.args.get('status')
    min_score = request.args.get('min_score', type=float)

    opportunities = db.get_all_opportunities(status=status, min_heat_score=min_score)
    return jsonify(opportunities)


@app.route('/api/opportunity/<int:opportunity_id>')
def api_opportunity(opportunity_id):
    """API endpoint for single opportunity."""
    opportunity = db.get_opportunity(opportunity_id)
    if not opportunity:
        return jsonify({'error': 'Not found'}), 404

    articles = db.get_opportunity_articles(opportunity_id)
    opportunity['articles'] = articles

    return jsonify(opportunity)


@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard stats."""
    stats = db.get_dashboard_stats()
    return jsonify(stats)


@app.route('/api/recalculate_scores', methods=['POST'])
def api_recalculate_scores():
    """API endpoint to recalculate all scores."""
    engine = ScoringEngine()
    updated_count = engine.recalculate_all_scores()
    return jsonify({'updated': updated_count})


# ============== RFP Routes ==============

@app.route('/rfps')
def rfps_list():
    """List all RFPs with filtering."""
    status_filter = request.args.get('status', 'open')
    relevant_only = request.args.get('relevant', 'true').lower() == 'true'
    category_filter = request.args.get('category')

    if status_filter == 'all':
        status_filter = None

    rfps = db.get_all_rfps(status=status_filter, relevant_only=relevant_only, category=category_filter)
    rfp_stats = db.get_rfp_stats()

    return render_template('rfps.html',
                         rfps=rfps,
                         stats=rfp_stats,
                         status_filter=status_filter,
                         relevant_only=relevant_only,
                         category_filter=category_filter)


@app.route('/rfp/<int:rfp_id>')
def rfp_detail(rfp_id):
    """Detailed view of a single RFP."""
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        flash('RFP not found', 'error')
        return redirect(url_for('rfps_list'))

    entity = None
    if rfp.get('entity_id'):
        entity = db.get_entity(rfp['entity_id'])

    return render_template('rfp_detail.html', rfp=rfp, entity=entity)


@app.route('/rfp/<int:rfp_id>/update', methods=['POST'])
def update_rfp_route(rfp_id):
    """Update RFP status or notes."""
    status = request.form.get('status')
    notes = request.form.get('notes')

    updates = {}
    if status:
        updates['status'] = status
    if notes is not None:
        updates['notes'] = notes

    if updates:
        db.update_rfp(rfp_id, **updates)
        flash('RFP updated successfully', 'success')

    return redirect(url_for('rfp_detail', rfp_id=rfp_id))


@app.route('/rfps/discover')
def rfp_discover_page():
    """RFP discovery management page."""
    rfp_stats = db.get_rfp_stats()
    keywords = db.get_rfp_keywords()

    return render_template('rfp_discover.html', stats=rfp_stats, keywords=keywords)


@app.route('/rfps/discover/run', methods=['POST'])
def run_rfp_discovery():
    """Run RFP discovery across procurement portals."""
    engine = RFPDiscoveryEngine()
    stats = engine.run_discovery()

    flash(f'RFP Discovery complete. Found {stats["total_found"]} RFPs, {stats["relevant_found"]} relevant.', 'success')
    return redirect(url_for('rfps_list'))


@app.route('/rfps/add', methods=['POST'])
def add_rfp_route():
    """Manually add an RFP."""
    url = request.form.get('url')
    title = request.form.get('title')
    agency = request.form.get('agency')
    due_date = request.form.get('due_date')

    if not url and not title:
        flash('Please provide a URL or title', 'error')
        return redirect(url_for('rfp_discover_page'))

    if url:
        rfp_id = manual_add_rfp(url, title=title, agency_name=agency, due_date=due_date)
    else:
        # Direct add without URL
        engine = RFPDiscoveryEngine()
        is_relevant, score, category = engine.calculate_relevance(title, '')
        entity_id = engine.match_entity(agency) if agency else None

        rfp_id = db.create_rfp(
            title=title,
            entity_id=entity_id,
            due_date=due_date,
            source_portal='manual',
            is_relevant=1 if is_relevant else 0,
            relevance_score=score,
            category=category
        )

    if rfp_id:
        flash('RFP added successfully', 'success')
        return redirect(url_for('rfp_detail', rfp_id=rfp_id))
    else:
        flash('Failed to add RFP', 'error')
        return redirect(url_for('rfp_discover_page'))


@app.route('/api/rfps')
def api_rfps():
    """API endpoint for RFPs."""
    status = request.args.get('status')
    relevant = request.args.get('relevant', 'true').lower() == 'true'

    rfps = db.get_all_rfps(status=status, relevant_only=relevant)
    return jsonify(rfps)


@app.route('/api/rfp/<int:rfp_id>')
def api_rfp(rfp_id):
    """API endpoint for single RFP."""
    rfp = db.get_rfp(rfp_id)
    if not rfp:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(rfp)


@app.route('/api/rfp_stats')
def api_rfp_stats():
    """API endpoint for RFP stats."""
    stats = db.get_rfp_stats()
    return jsonify(stats)


# ============== Initialization ==============

def init_app():
    """Initialize the application."""
    db.init_database()
    db.seed_keywords()
    db.seed_sources()
    db.seed_rfp_keywords()
    logger.info("Application initialized")


if __name__ == '__main__':
    init_app()
    app.run(debug=True, port=5003)
