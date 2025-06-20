# strategy.py

def generate_strategy(objective, scale, audience, investment, metrics, ai_categories):
    """
    Generates a complete strategic profile for an event.

    This function provides a comparable event profile, prioritizes metrics based
    on the campaign objective, and generates strategic advice based on the
    relationship between investment and metric choice.

    Args:
        objective (str): The primary campaign goal.
        scale (str): The campaign's scale.
        audience (str): The target audience.
        investment (str): The campaign's investment level.
        metrics (list): A list of the user's selected metrics.
        ai_categories (dict): A dictionary mapping metrics to their AI-generated category.

    Returns:
        dict: A dictionary containing the ideal profile, prioritized metrics, and guidance notes.
    """
    
    # --- Part 1: Define Comparable Event Profile (As before) ---
    profile_description = (
        f"Based on your inputs, you should look for past events that were also "
        f"'{scale}' scale, focused on '{audience}', "
        f"with a primary objective of '{objective}'."
    )
    
    hierarchy_notes = [
        {"title": "Priority #1: Match by Objective", "text": "..."},
        {"title": "Priority #2: Match by Scale", "text": "..."},
        {"title": "Priority #3: Match by Audience", "text": "..."}
    ] # Text truncated for brevity, logic remains the same.

    # --- Part 2: Prioritize Metrics based on Objective ---
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

    # --- Part 3: Generate Strategic Considerations based on Investment ---
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
        "ideal_profile_description": profile_description,
        "hierarchy_notes": hierarchy_notes,
        "prioritized_metrics": prioritized_metrics,
        "strategic_considerations": considerations
    }
