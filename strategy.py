# strategy.py

def generate_strategy(objective, investment, metrics, ai_categories):
    """
    Generates strategic advice based on event profile and selected metrics.
    This function is isolated and its output is for user guidance only.

    Args:
        objective (str): The primary campaign goal.
        investment (str): The campaign's investment level.
        metrics (list): A list of the user's selected metrics.
        ai_categories (dict): A dictionary mapping metrics to their AI-generated category.

    Returns:
        dict: A dictionary containing prioritized metrics and strategic considerations.
    """
    
    # --- Part 1: Prioritize Metrics based on Objective ---
    prioritized_metrics = []
    priority_map = {
        "Brand Awareness / Reach":      {"Reach": "High", "Depth": "Medium", "Action": "Low"},
        "Audience Engagement / Depth":  {"Depth": "High", "Reach": "Medium", "Action": "Low"},
        "Conversion / Action":          {"Action": "High", "Depth": "Medium", "Reach": "Low"}
    }
    current_priority_scheme = priority_map.get(objective, {})

    for metric in metrics:
        category = ai_categories.get(metric, "Uncategorized")
        priority = current_priority_scheme.get(category, "Medium")
        prioritized_metrics.append({
            "Metric": metric,
            "Category": category,
            "Priority": priority
        })

    # --- Part 2: Generate Strategic Considerations based on Investment ---
    considerations = []
    high_cost_metrics = ["Press UMV (unique monthly views)", "Social Impressions"]
    
    if investment == 'Low (<$50k)':
        costly_metrics_selected = [m for m in metrics if m in high_cost_metrics]
        if costly_metrics_selected:
            considerations.append({
                "type": "Warning",
                "text": f"With a 'Low' investment, achieving high performance for costly metrics like {', '.join(costly_metrics_selected)} can be challenging. Focus on organic growth and efficiency."
            })

    if investment == 'Major (>$1M)' and not any(p['Category'] == 'Reach' for p in prioritized_metrics):
         considerations.append({
                "type": "Info",
                "text": "For a 'Major' investment campaign, consider adding more 'Reach' metrics to ensure you are measuring the full impact of your spend on top-of-funnel awareness."
            })

    if objective == 'Conversion / Action' and not any(p['Category'] == 'Action' for p in prioritized_metrics):
        considerations.append({
                "type": "Warning",
                "text": "Your objective is 'Conversion / Action', but no 'Action' metrics are selected. Ensure you add metrics that directly measure your conversion goals (e.g., sign-ups, downloads)."
            })

    return {
        "prioritized_metrics": prioritized_metrics,
        "strategic_considerations": considerations
    }
