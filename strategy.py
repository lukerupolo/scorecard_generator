# strategy.py

def define_comparable_profile(objective, scale, audience):
    """
    Generates a profile for comparable events based on strategic inputs.

    This function provides a clear, hierarchical guide for selecting appropriate
    past events to use for benchmarking, based on core marketing principles.

    Args:
        objective (str): The primary goal of the campaign (e.g., 'Brand Awareness / Reach').
        scale (str): The scale and investment level of the campaign (e.g., 'Major', 'Standard').
        audience (str): The target audience of the campaign (e.g., 'New Customer Acquisition').

    Returns:
        dict: A dictionary containing the ideal profile description and prioritized guidance notes.
    """
    profile_description = (
        f"Based on your inputs, you should look for past events that were also "
        f"'{scale}' scale, focused on '{audience}', "
        f"with a primary objective of '{objective}'."
    )

    guidance_notes = [
        {
            "title": "Priority #1: Match by Objective",
            "text": "The goal of the campaign is the most important factor. An 'Awareness' campaign will have fundamentally different results from a 'Conversion' campaign. Ensure the past events you choose had the same primary objective."
        },
        {
            "title": "Priority #2: Match by Scale & Investment",
            "text": "A 'Major' multi-million dollar launch is not comparable to a 'Niche' community initiative. Comparing events of a similar scale is critical for a credible benchmark."
        },
        {
            "title": "Priority #3: Match by Target Audience",
            "text": "Campaigns targeting new users ('Acquisition') often have lower conversion rates but higher reach than campaigns targeting existing fans ('Re-engagement'). Choose past events that had a similar audience focus."
        }
    ]

    return {
        "ideal_profile_description": profile_description,
        "guidance_notes": guidance_notes
    }
