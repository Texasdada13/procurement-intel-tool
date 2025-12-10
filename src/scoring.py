"""
Scoring Engine for Procurement Intelligence Tool.
Calculates and updates heat scores for opportunities based on multiple factors.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from . import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScoringEngine:
    """Engine for calculating opportunity heat scores."""

    # Weights for different scoring factors
    WEIGHTS = {
        'keyword_score': 0.35,      # Base score from keyword matches
        'recency': 0.25,            # How recent the issue is
        'article_count': 0.15,      # Number of articles about the issue
        'severity': 0.15,           # Severity based on issue type
        'entity_size': 0.10,        # Larger entities = bigger opportunity
    }

    # Severity multipliers by issue type
    SEVERITY_MULTIPLIERS = {
        'legal': 1.5,        # Legal issues are most severe
        'procurement': 1.3,  # Procurement violations are core target
        'ethics': 1.2,       # Ethics issues indicate systemic problems
        'audit': 1.1,        # Audit findings show gaps
        'budget': 1.0,       # Budget issues are common
    }

    # Priority thresholds
    PRIORITY_THRESHOLDS = {
        'urgent': 85,
        'high': 70,
        'medium': 40,
        'low': 0,
    }

    def calculate_recency_score(self, first_detected: datetime) -> float:
        """
        Calculate recency score (0-100).
        More recent = higher score.
        """
        if not first_detected:
            return 50  # Default middle score

        if isinstance(first_detected, str):
            first_detected = datetime.fromisoformat(first_detected.replace('Z', '+00:00'))

        days_old = (datetime.now() - first_detected.replace(tzinfo=None)).days

        if days_old <= 7:
            return 100
        elif days_old <= 14:
            return 90
        elif days_old <= 30:
            return 75
        elif days_old <= 60:
            return 50
        elif days_old <= 90:
            return 30
        else:
            return 10

    def calculate_article_count_score(self, article_count: int) -> float:
        """
        Calculate score based on number of articles.
        More articles = more attention = hotter lead.
        """
        if article_count >= 10:
            return 100
        elif article_count >= 5:
            return 80
        elif article_count >= 3:
            return 60
        elif article_count >= 2:
            return 40
        else:
            return 20

    def calculate_severity_score(self, issue_type: str) -> float:
        """Calculate severity score based on issue type."""
        multiplier = self.SEVERITY_MULTIPLIERS.get(issue_type, 1.0)
        return min(100, 70 * multiplier)

    def calculate_entity_size_score(self, entity: Dict) -> float:
        """
        Calculate score based on entity size.
        Larger entities = bigger contracts = bigger opportunity.
        """
        population = entity.get('population', 0) or 0
        budget = entity.get('annual_budget', 0) or 0

        # Score based on population
        if population >= 500000:
            pop_score = 100
        elif population >= 200000:
            pop_score = 80
        elif population >= 100000:
            pop_score = 60
        elif population >= 50000:
            pop_score = 40
        else:
            pop_score = 20

        # Score based on budget (if available)
        if budget >= 1000000000:  # $1B+
            budget_score = 100
        elif budget >= 500000000:  # $500M+
            budget_score = 80
        elif budget >= 100000000:  # $100M+
            budget_score = 60
        elif budget > 0:
            budget_score = 40
        else:
            budget_score = 0

        # Use whichever is higher, or average if both available
        if budget_score > 0 and pop_score > 0:
            return (pop_score + budget_score) / 2
        return max(pop_score, budget_score) if budget_score > 0 else pop_score

    def calculate_heat_score(self, opportunity: Dict, articles: List[Dict] = None,
                             entity: Dict = None) -> float:
        """
        Calculate comprehensive heat score for an opportunity.
        Returns score from 0-100.
        """
        scores = {}

        # Keyword score (use existing score from discovery)
        scores['keyword_score'] = opportunity.get('heat_score', 50)

        # Recency score
        scores['recency'] = self.calculate_recency_score(opportunity.get('first_detected'))

        # Article count score
        article_count = len(articles) if articles else 1
        scores['article_count'] = self.calculate_article_count_score(article_count)

        # Severity score
        scores['severity'] = self.calculate_severity_score(opportunity.get('issue_type'))

        # Entity size score
        if entity:
            scores['entity_size'] = self.calculate_entity_size_score(entity)
        else:
            scores['entity_size'] = 50  # Default

        # Calculate weighted average
        total_score = sum(
            scores[factor] * self.WEIGHTS[factor]
            for factor in self.WEIGHTS
        )

        return round(min(100, max(0, total_score)), 1)

    def determine_priority(self, heat_score: float) -> str:
        """Determine priority level based on heat score."""
        for priority, threshold in sorted(self.PRIORITY_THRESHOLDS.items(),
                                         key=lambda x: x[1], reverse=True):
            if heat_score >= threshold:
                return priority
        return 'low'

    def update_opportunity_score(self, opportunity_id: int) -> Dict:
        """
        Recalculate and update the heat score for an opportunity.
        Returns updated opportunity data.
        """
        opportunity = db.get_opportunity(opportunity_id)
        if not opportunity:
            return None

        # Get related data
        articles = db.get_opportunity_articles(opportunity_id)
        entity = db.get_entity(opportunity['entity_id'])

        # Calculate new score
        new_score = self.calculate_heat_score(opportunity, articles, entity)
        new_priority = self.determine_priority(new_score)

        # Update if changed
        if new_score != opportunity['heat_score'] or new_priority != opportunity['priority']:
            db.update_opportunity(opportunity_id, heat_score=new_score, priority=new_priority)
            db.add_activity_log(
                opportunity_id,
                'score_updated',
                f'Heat score updated from {opportunity["heat_score"]} to {new_score}'
            )

        opportunity['heat_score'] = new_score
        opportunity['priority'] = new_priority
        return opportunity

    def recalculate_all_scores(self) -> int:
        """
        Recalculate scores for all opportunities.
        Returns count of updated opportunities.
        """
        opportunities = db.get_all_opportunities()
        updated_count = 0

        for opp in opportunities:
            old_score = opp['heat_score']
            updated = self.update_opportunity_score(opp['id'])
            if updated and updated['heat_score'] != old_score:
                updated_count += 1

        logger.info(f"Recalculated scores for {len(opportunities)} opportunities, {updated_count} updated")
        return updated_count


def get_score_breakdown(opportunity_id: int) -> Dict:
    """
    Get detailed breakdown of how an opportunity's score was calculated.
    Useful for displaying in the UI.
    """
    opportunity = db.get_opportunity(opportunity_id)
    if not opportunity:
        return None

    articles = db.get_opportunity_articles(opportunity_id)
    entity = db.get_entity(opportunity['entity_id'])

    engine = ScoringEngine()

    breakdown = {
        'opportunity_id': opportunity_id,
        'final_score': opportunity['heat_score'],
        'priority': opportunity['priority'],
        'factors': {
            'keyword_score': {
                'raw_score': opportunity.get('heat_score', 50),
                'weight': engine.WEIGHTS['keyword_score'],
                'weighted_score': opportunity.get('heat_score', 50) * engine.WEIGHTS['keyword_score']
            },
            'recency': {
                'raw_score': engine.calculate_recency_score(opportunity.get('first_detected')),
                'weight': engine.WEIGHTS['recency'],
                'weighted_score': engine.calculate_recency_score(opportunity.get('first_detected')) * engine.WEIGHTS['recency']
            },
            'article_count': {
                'raw_score': engine.calculate_article_count_score(len(articles) if articles else 1),
                'weight': engine.WEIGHTS['article_count'],
                'article_count': len(articles) if articles else 1,
                'weighted_score': engine.calculate_article_count_score(len(articles) if articles else 1) * engine.WEIGHTS['article_count']
            },
            'severity': {
                'raw_score': engine.calculate_severity_score(opportunity.get('issue_type')),
                'weight': engine.WEIGHTS['severity'],
                'issue_type': opportunity.get('issue_type'),
                'weighted_score': engine.calculate_severity_score(opportunity.get('issue_type')) * engine.WEIGHTS['severity']
            },
            'entity_size': {
                'raw_score': engine.calculate_entity_size_score(entity) if entity else 50,
                'weight': engine.WEIGHTS['entity_size'],
                'weighted_score': (engine.calculate_entity_size_score(entity) if entity else 50) * engine.WEIGHTS['entity_size']
            }
        }
    }

    return breakdown


if __name__ == '__main__':
    # Recalculate all scores
    engine = ScoringEngine()
    engine.recalculate_all_scores()
