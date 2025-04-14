from django.db.models import Avg, Count
from .models import FormResponse, Answer, Question

def calculate_team_scores(form, team):
    """
    Calculate average scores for a team across all likert questions
    Returns a dictionary with:
    - team_average: overall team average
    - member_scores: individual member averages
    - question_averages: average per question
    """
    # Get all likert questions for this form
    likert_questions = form.template.questions.filter(question_type='likert')
    
    # Get all responses for this team
    responses = FormResponse.objects.filter(
        form=form,
        evaluator__teams=team,
        submitted=True
    ).prefetch_related('answers')
    
    # Calculate team average
    team_average = responses.filter(
        answers__question__in=likert_questions
    ).aggregate(avg_score=Avg('answers__likert_answer'))['avg_score'] or 0
    
    # Calculate member averages
    member_scores = {}
    for member in team.members.all():
        # Get responses received by this member
        member_responses = responses.filter(evaluatee=member)
        
        # Calculate average score received
        member_avg = member_responses.filter(
            answers__question__in=likert_questions
        ).aggregate(avg_score=Avg('answers__likert_answer'))['avg_score'] or 0
        
        # Get completion stats
        total_evaluations = member_responses.count()
        completed_evaluations = member_responses.filter(submitted=True).count()
        
        member_scores[member] = {
            'average_score': member_avg,
            'completion': f"{completed_evaluations}/{total_evaluations}",
            'responses': member_responses
        }
    
    # Calculate question averages
    question_averages = {}
    for question in likert_questions:
        avg = responses.filter(
            answers__question=question
        ).aggregate(avg_score=Avg('answers__likert_answer'))['avg_score'] or 0
        question_averages[question] = avg
    
    return {
        'team_average': team_average,
        'member_scores': member_scores,
        'question_averages': question_averages
    }

def get_score_color(score):
    """Return color class based on score range"""
    if score >= 4:
        return 'score-high'
    elif score >= 2.5:
        return 'score-medium'
    else:
        return 'score-low'

def get_member_feedback(form, member):
    """
    Get all feedback for a specific member
    Returns a dictionary with:
    - likert_questions: average scores per question
    - text_responses: all text feedback
    """
    # Get all responses for this member
    responses = FormResponse.objects.filter(
        form=form,
        evaluatee=member,
        submitted=True
    ).prefetch_related('answers__question')
    
    # Get likert questions and calculate averages
    likert_questions = {}
    for question in form.template.questions.filter(question_type='likert'):
        avg = responses.filter(
            answers__question=question
        ).aggregate(avg_score=Avg('answers__likert_answer'))['avg_score'] or 0
        likert_questions[question] = {
            'average': avg,
            'color': get_score_color(avg)
        }
    
    # Get all text responses
    text_responses = []
    for response in responses:
        text_answers = response.answers.filter(question__question_type='open')
        if text_answers.exists():
            text_responses.append({
                'evaluator': response.evaluator,
                'answers': text_answers
            })
    
    return {
        'likert_questions': likert_questions,
        'text_responses': text_responses
    } 