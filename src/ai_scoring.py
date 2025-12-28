"""
AI-Powered Relevance Scoring for RFPs.
Uses various AI techniques to better score RFP relevance.

Supports:
- OpenAI GPT (if API key available)
- Local keyword-based ML scoring (always available)
- Semantic similarity scoring (with sentence-transformers)
"""

import os
import sys
import logging
import re
from typing import List, Dict, Optional, Tuple
from collections import Counter

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db

logger = logging.getLogger(__name__)

# Check for optional AI libraries
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class KeywordScorer:
    """
    Advanced keyword-based scoring with TF-IDF like weighting.
    Always available, no external dependencies.
    """

    # Expanded keyword sets with weights
    HIGH_VALUE_KEYWORDS = {
        # IT Consulting - highest value
        'application rationalization': 5.0,
        'it assessment': 4.5,
        'technology assessment': 4.5,
        'digital transformation': 4.5,
        'it modernization': 4.5,
        'enterprise architecture': 4.5,
        'it strategic plan': 4.5,
        'systems integration': 4.0,
        'technology roadmap': 4.0,

        # Cybersecurity
        'cybersecurity assessment': 4.5,
        'security audit': 4.0,
        'penetration testing': 4.0,
        'vulnerability assessment': 4.0,
        'security consulting': 4.0,

        # Cloud & Infrastructure
        'cloud migration': 4.0,
        'cloud assessment': 4.0,
        'infrastructure assessment': 4.0,
        'network assessment': 3.5,
        'data center': 3.5,

        # Software & ERP
        'erp implementation': 4.5,
        'erp assessment': 4.5,
        'software implementation': 4.0,
        'system implementation': 4.0,
        'financial system': 3.5,
        'hris': 3.5,

        # Studies & Analysis
        'feasibility study': 4.0,
        'needs assessment': 4.0,
        'gap analysis': 4.0,
        'business process': 3.5,
        'process improvement': 3.5,
        'workflow analysis': 3.5,
        'requirements analysis': 3.5,

        # Data & Analytics
        'data analytics': 4.0,
        'business intelligence': 4.0,
        'data governance': 4.0,
        'data migration': 3.5,
        'reporting system': 3.0,

        # General Consulting
        'management consulting': 3.5,
        'organizational assessment': 3.5,
        'strategic planning': 3.5,
        'operational review': 3.5,
        'performance audit': 3.5,
    }

    MEDIUM_VALUE_KEYWORDS = {
        'consulting': 2.0,
        'assessment': 2.0,
        'analysis': 2.0,
        'evaluation': 2.0,
        'study': 2.0,
        'review': 1.5,
        'planning': 1.5,
        'implementation': 2.0,
        'integration': 2.0,
        'software': 2.0,
        'system': 1.5,
        'technology': 2.0,
        'digital': 2.0,
        'data': 1.5,
        'information': 1.5,
        'network': 1.5,
        'security': 2.0,
        'cloud': 2.0,
        'infrastructure': 2.0,
        'modernization': 2.5,
        'upgrade': 1.5,
    }

    NEGATIVE_KEYWORDS = {
        # Construction & Physical
        'construction': -3.0,
        'building': -2.0,
        'renovation': -3.0,
        'roofing': -4.0,
        'paving': -4.0,
        'landscaping': -4.0,
        'plumbing': -4.0,
        'electrical work': -3.0,
        'hvac': -3.0,
        'flooring': -4.0,

        # Physical Services
        'janitorial': -4.0,
        'cleaning': -3.0,
        'mowing': -5.0,
        'lawn care': -5.0,
        'pest control': -4.0,
        'waste removal': -4.0,
        'debris removal': -4.0,

        # Vehicles & Equipment
        'vehicle': -3.0,
        'fleet': -2.5,
        'heavy equipment': -3.0,
        'machinery': -3.0,

        # Commodities
        'uniforms': -4.0,
        'office supplies': -3.0,
        'fuel': -4.0,
        'chemicals': -3.0,
        'paper products': -4.0,
    }

    def __init__(self):
        """Initialize the keyword scorer."""
        self.all_keywords = {}
        self.all_keywords.update(self.HIGH_VALUE_KEYWORDS)
        self.all_keywords.update(self.MEDIUM_VALUE_KEYWORDS)
        self.all_keywords.update(self.NEGATIVE_KEYWORDS)

    def score_text(self, text: str) -> Tuple[float, List[Dict]]:
        """
        Score text based on keyword presence and weights.

        Args:
            text: Text to score

        Returns:
            Tuple of (score, list of matched keywords with weights)
        """
        if not text:
            return 0.0, []

        text_lower = text.lower()
        matches = []
        total_score = 0.0

        # Check each keyword
        for keyword, weight in self.all_keywords.items():
            count = text_lower.count(keyword.lower())
            if count > 0:
                # Diminishing returns for multiple occurrences
                keyword_score = weight * (1 + 0.2 * (count - 1))
                total_score += keyword_score
                matches.append({
                    'keyword': keyword,
                    'weight': weight,
                    'count': count,
                    'score': keyword_score
                })

        # Normalize score to 0-100 range
        # Typical high-value RFP might score 15-25 raw
        normalized_score = min(100, max(0, (total_score / 25) * 100))

        return normalized_score, sorted(matches, key=lambda x: x['score'], reverse=True)

    def categorize_rfp(self, text: str) -> str:
        """
        Categorize an RFP based on content.

        Args:
            text: RFP text

        Returns:
            Category string
        """
        text_lower = text.lower()

        categories = {
            'it_consulting': ['it assessment', 'technology assessment', 'it consulting',
                            'digital transformation', 'it modernization', 'technology roadmap'],
            'cybersecurity': ['cybersecurity', 'security audit', 'penetration testing',
                            'vulnerability', 'security assessment'],
            'software': ['software implementation', 'erp', 'system implementation',
                       'software development', 'application'],
            'cloud': ['cloud migration', 'cloud computing', 'cloud services',
                    'aws', 'azure', 'infrastructure'],
            'data': ['data analytics', 'business intelligence', 'data governance',
                   'database', 'data warehouse', 'reporting'],
            'professional_services': ['consulting', 'assessment', 'study',
                                    'analysis', 'planning', 'review'],
        }

        category_scores = {}
        for category, keywords in categories.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                category_scores[category] = score

        if category_scores:
            return max(category_scores, key=category_scores.get)

        return 'general'


class SemanticScorer:
    """
    Semantic similarity scoring using sentence transformers.
    Compares RFP text to ideal target descriptions.
    """

    # Ideal RFP descriptions for similarity matching
    TARGET_DESCRIPTIONS = [
        "IT consulting services for technology assessment and digital transformation",
        "Enterprise architecture consulting and IT strategic planning",
        "Cybersecurity assessment and security audit services",
        "Cloud migration consulting and infrastructure modernization",
        "ERP system implementation and software consulting",
        "Data analytics and business intelligence consulting",
        "Application rationalization and IT modernization study",
        "Management consulting for technology and organizational improvement"
    ]

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the semantic scorer.

        Args:
            model_name: Sentence transformer model to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError("sentence-transformers not installed. Run: pip install sentence-transformers")

        self.model = SentenceTransformer(model_name)
        self.target_embeddings = self.model.encode(self.TARGET_DESCRIPTIONS)

    def score_text(self, text: str) -> Tuple[float, str]:
        """
        Score text using semantic similarity.

        Args:
            text: Text to score

        Returns:
            Tuple of (score, most similar target description)
        """
        if not text:
            return 0.0, ""

        # Truncate very long text
        text = text[:2000]

        # Encode the input text
        text_embedding = self.model.encode([text])[0]

        # Calculate similarities
        similarities = util.cos_sim(text_embedding, self.target_embeddings)[0]

        # Get best match
        best_idx = similarities.argmax().item()
        best_score = similarities[best_idx].item()
        best_match = self.TARGET_DESCRIPTIONS[best_idx]

        # Convert to 0-100 scale (similarity is typically 0-1)
        normalized_score = best_score * 100

        return normalized_score, best_match


class OpenAIScorer:
    """
    OpenAI GPT-based scoring for RFP relevance.
    Provides natural language analysis.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize the OpenAI scorer.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai not installed. Run: pip install openai")

        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")

        openai.api_key = self.api_key

    def score_rfp(self, title: str, description: str = None) -> Dict:
        """
        Score an RFP using OpenAI.

        Args:
            title: RFP title
            description: RFP description

        Returns:
            Dict with score, category, and analysis
        """
        prompt = f"""Analyze this government RFP for relevance to IT consulting services.

RFP Title: {title}
{f'Description: {description[:1000]}' if description else ''}

Rate the relevance from 0-100 based on:
- Is this IT, technology, or consulting related?
- Is this a good opportunity for a consulting firm?
- Exclude construction, physical services, commodities

Respond in this exact JSON format:
{{"score": <0-100>, "category": "<category>", "reason": "<brief reason>", "key_services": ["<service1>", "<service2>"]}}"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            import json
            result = json.loads(result_text)

            return {
                'score': float(result.get('score', 0)),
                'category': result.get('category', 'unknown'),
                'reason': result.get('reason', ''),
                'key_services': result.get('key_services', []),
                'model': 'gpt-3.5-turbo'
            }

        except Exception as e:
            logger.error(f"OpenAI scoring failed: {e}")
            return {
                'score': 0,
                'error': str(e)
            }


class AIRelevanceScorer:
    """
    Combined AI relevance scorer using multiple methods.
    Falls back gracefully based on available libraries.
    """

    def __init__(self, use_openai: bool = False, use_semantic: bool = False):
        """
        Initialize the combined scorer.

        Args:
            use_openai: Enable OpenAI scoring (requires API key)
            use_semantic: Enable semantic similarity scoring
        """
        self.keyword_scorer = KeywordScorer()
        self.semantic_scorer = None
        self.openai_scorer = None

        if use_semantic and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.semantic_scorer = SemanticScorer()
                logger.info("Semantic scoring enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic scorer: {e}")

        if use_openai and OPENAI_AVAILABLE and os.environ.get('OPENAI_API_KEY'):
            try:
                self.openai_scorer = OpenAIScorer()
                logger.info("OpenAI scoring enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI scorer: {e}")

    def score_rfp(self, title: str, description: str = None) -> Dict:
        """
        Score an RFP using all available methods.

        Args:
            title: RFP title
            description: RFP description

        Returns:
            Combined scoring result
        """
        text = f"{title} {description or ''}"

        result = {
            'title': title,
            'methods_used': []
        }

        # Keyword scoring (always available)
        kw_score, kw_matches = self.keyword_scorer.score_text(text)
        result['keyword_score'] = kw_score
        result['keyword_matches'] = kw_matches[:10]  # Top 10 matches
        result['category'] = self.keyword_scorer.categorize_rfp(text)
        result['methods_used'].append('keyword')

        scores = [kw_score]

        # Semantic scoring
        if self.semantic_scorer:
            try:
                sem_score, best_match = self.semantic_scorer.score_text(text)
                result['semantic_score'] = sem_score
                result['semantic_match'] = best_match
                result['methods_used'].append('semantic')
                scores.append(sem_score)
            except Exception as e:
                logger.warning(f"Semantic scoring failed: {e}")

        # OpenAI scoring
        if self.openai_scorer:
            try:
                ai_result = self.openai_scorer.score_rfp(title, description)
                result['openai_score'] = ai_result.get('score', 0)
                result['openai_reason'] = ai_result.get('reason', '')
                result['openai_services'] = ai_result.get('key_services', [])
                result['methods_used'].append('openai')
                if ai_result.get('score'):
                    scores.append(ai_result['score'])
            except Exception as e:
                logger.warning(f"OpenAI scoring failed: {e}")

        # Calculate combined score (weighted average)
        if len(scores) == 1:
            result['final_score'] = scores[0]
        elif len(scores) == 2:
            result['final_score'] = (scores[0] * 0.4 + scores[1] * 0.6)
        else:
            # Keyword: 30%, Semantic: 35%, OpenAI: 35%
            result['final_score'] = (scores[0] * 0.3 + scores[1] * 0.35 + scores[2] * 0.35)

        result['is_relevant'] = result['final_score'] >= 40

        return result

    def rescore_all_rfps(self) -> Dict:
        """
        Rescore all RFPs in the database.

        Returns:
            Scoring statistics
        """
        rfps = db.get_all_rfps()

        stats = {
            'total': len(rfps),
            'rescored': 0,
            'high_relevance': 0,
            'medium_relevance': 0,
            'low_relevance': 0
        }

        for rfp in rfps:
            try:
                result = self.score_rfp(rfp['title'], rfp.get('description'))

                # Update database
                db.update_rfp(rfp['id'],
                             relevance_score=result['final_score'],
                             is_relevant=1 if result['is_relevant'] else 0,
                             category=result.get('category'))

                stats['rescored'] += 1

                if result['final_score'] >= 70:
                    stats['high_relevance'] += 1
                elif result['final_score'] >= 40:
                    stats['medium_relevance'] += 1
                else:
                    stats['low_relevance'] += 1

            except Exception as e:
                logger.error(f"Failed to rescore RFP {rfp['id']}: {e}")

        return stats


def score_rfp(title: str, description: str = None) -> Dict:
    """Convenience function to score an RFP."""
    scorer = AIRelevanceScorer()
    return scorer.score_rfp(title, description)


def rescore_all_rfps() -> Dict:
    """Convenience function to rescore all RFPs."""
    scorer = AIRelevanceScorer()
    return scorer.rescore_all_rfps()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("AI Relevance Scoring Test")
    print(f"OpenAI available: {OPENAI_AVAILABLE}")
    print(f"Sentence Transformers available: {SENTENCE_TRANSFORMERS_AVAILABLE}")

    # Test scoring
    test_cases = [
        "IT Assessment and Technology Modernization Study",
        "Enterprise Resource Planning (ERP) System Implementation",
        "Janitorial Services for County Buildings",
        "Cybersecurity Audit and Vulnerability Assessment",
        "Lawn Care and Landscaping Maintenance",
        "Cloud Migration and Infrastructure Assessment Consulting"
    ]

    scorer = AIRelevanceScorer()

    for title in test_cases:
        result = scorer.score_rfp(title)
        print(f"\n{title}")
        print(f"  Score: {result['final_score']:.1f}")
        print(f"  Category: {result.get('category', 'N/A')}")
        print(f"  Relevant: {result['is_relevant']}")
