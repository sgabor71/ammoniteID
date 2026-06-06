def build_result(
    combined: dict,
    num_photos: int
) -> dict:
    """
    Takes combined scores and builds the full
    structured result with scenario, genus breakdown
    and formatted output.
    
    Scenarios (4 tiers):
    - 'likely':        ≥80% confidence - high confidence identification
    - 'possible':      60-79% confidence - medium confidence, still useful
    - 'low':           30-59% confidence - low confidence but give best guess
    - 'uncertain':     ≤29% confidence - too noisy, don't try
    - 'non_ammonite':  Non-ammonite detection
    """
    family_scores    = combined['family_scores']
    non_am_total     = combined['non_am_total']
    top_non_am       = combined['top_non_am']
    genus_scores     = combined['genus_scores']

    top_family       = max(
        family_scores, key=family_scores.get
    )
    top_family_score = family_scores[top_family] * 100
    top_non_am_score = combined['non_am_scores'][top_non_am]

    # ── Determine scenario (4 tiers + non-ammonite) ───────────────────
    print(f"NON-AM DEBUG: non_am_total={non_am_total}, non_am*100={non_am_total * 100}, top_family_score={top_family_score}")
    
    if non_am_total * 100 > top_family_score:
        scenario = 'non_ammonite'
    elif top_family_score >= FAMILY_LIKELY_THRESHOLD:
        scenario = 'likely'      # ≥80% - high confidence
    elif top_family_score >= FAMILY_POSSIBLE_THRESHOLD:
        scenario = 'possible'    # 60-79% - medium confidence
    elif top_family_score >= FAMILY_LOW_THRESHOLD:
        scenario = 'low'         # 30-59% - low confidence but give best guess
    else:
        scenario = 'uncertain'   # ≤29% - too noisy

    print(f"SCENARIO DEBUG: scenario={scenario}, score={top_family_score}")

    # ── Build genus breakdown (show for likely, possible, AND low) ───
    genus_breakdown = []
    if scenario in ('likely', 'possible', 'low'):
        family_genera = FAMILY_TO_GENERA[top_family]
        family_total = family_scores[top_family]

        for genus in family_genera:
            raw  = genus_scores.get(genus, 0.0)
            norm = (
                raw / family_total
                if family_total > 0 else 0.0
            )
            print(f"GENUS DEBUG: {genus} = {norm}")
            genus_breakdown.append({
                'genus':            genus,
                'normalised_score': norm,
                'bar':              build_bar(norm),
                'wording':          get_genus_wording(norm),
                'percentage':       round(norm * 100),
            })

        genus_breakdown.sort(
            key=lambda x: x['normalised_score'],
            reverse=True
        )

    # ── Build the result dictionary ────────────────────────────────
    result = {
        'scenario':         scenario,
        'num_photos':       num_photos,
        'top_family':       top_family,
        'top_family_score': round(top_family_score),
        'family_scores': {
            k: round(v, 1)
            for k, v in family_scores.items()
        },
        'genus_breakdown':  genus_breakdown,
        'non_am_total':     round(non_am_total * 100),
        'top_non_am':       top_non_am,
        'top_non_am_score': round(top_non_am_score * 100),
        'non_am_category':  NON_AMMONITE_MAP.get(top_non_am, 'Other_Fossil'),
        'non_am_display':   NON_AM_DISPLAY.get(top_non_am, top_non_am),
    }

    # Generate confidence labels with new thresholds
    def get_confidence_label(score):
        if score >= 80:
            return "HIGH ✅"
        elif score >= 60:
            return "MODERATE ⚠️"
        elif score >= 30:
            return "LOW ⚠️"
        else:
            return "VERY LOW ❌"
    
    # Extract genus score for labels
    if genus_breakdown and len(genus_breakdown) > 0:
        top_genus_score = genus_breakdown[0].get('percentage', 0)
    else:
        top_genus_score = 0
    
    # Generate scenario-specific messaging
    if scenario == 'non_ammonite':
        score_for_message = round(non_am_total * 100)
        result['family_label'] = get_confidence_label(score_for_message)
        result['genus_label'] = None
        result['feedback_message'] = "💡 If you believe this is actually an ammonite, try retaking with the spiral/coiling pattern clearly visible"
        result['feedback_style'] = "info"
    
    elif scenario == 'uncertain':
        result['family_label'] = "VERY LOW ❌"
        result['genus_label'] = None
        result['feedback_message'] = "⚠️ Image too unclear for identification. Please retake with: fossil filling 80%+ of frame, even lighting, sharp focus"
        result['feedback_style'] = "warning"
    
    elif scenario == 'low':
        result['family_label'] = get_confidence_label(top_family_score)
        result['genus_label'] = get_confidence_label(top_genus_score) if top_genus_score else "LOW ⚠️"
        result['feedback_message'] = f"⚠️ Low confidence ({round(top_family_score)}%) - this is our best guess. For better results, retake with fossil filling 80%+ of frame and even lighting"
        result['feedback_style'] = "warning"
    
    elif scenario == 'possible':
        result['family_label'] = get_confidence_label(top_family_score)
        result['genus_label'] = get_confidence_label(top_genus_score) if top_genus_score else "MODERATE ⚠️"
        result['feedback_message'] = "💡 This result is likely correct. For better accuracy, try adding another photo rotated 30-90°"
        result['feedback_style'] = "info"
    
    else:  # 'likely'
        result['family_label'] = get_confidence_label(top_family_score)
        result['genus_label'] = get_confidence_label(top_genus_score) if top_genus_score else "HIGH ✅"
        result['feedback_message'] = "✅ High confidence identification"
        result['feedback_style'] = "success"

    result['formatted_output'] = format_output(result)
    return result


def format_output(result: dict) -> str:
    """
    Produces the agreed display text for the app.
    Handles all seven output scenarios (likely, possible, low, uncertain, non_ammonite).
    """
    scenario   = result['scenario']
    num_photos = result.get('num_photos', 1)
    lines      = []

    # ── Scenarios 1, 2, 3: Ammonite identified (likely, possible, low) ──
    if scenario in ('likely', 'possible', 'low'):
        family    = result['top_family']
        score_pct = result['top_family_score']
        
        # Choose wording based on scenario
        if scenario == 'likely':
            wording = 'Likely'
        elif scenario == 'possible':
            wording = 'Possible'
        else:  # 'low'
            wording = 'Best Guess'

        lines.append(
            f"FAMILY:  {family}"
            f"     [{wording} — {score_pct}% confidence]"
        )

        if num_photos > 1:
            lines.append(
                f"         Based on {num_photos} photographs"
            )
        
        # Add warning for low confidence
        if scenario == 'low':
            lines.append("")
            lines.append("⚠️  LOW CONFIDENCE IDENTIFICATION  ⚠️")
            lines.append("    This is our best estimate - the image may be:")
            lines.append("    - Too far away (fossil not filling the frame)")
            lines.append("    - Poorly lit or out of focus")
            lines.append("    - Taken at an angle obscuring key features")

        lines.append("")
        lines.append("GENUS:")

        for g in result['genus_breakdown']:
            lines.append(
                f"  {g['genus']:<28}"
                f"  {g['bar']}  {g['wording']}"
            )

        lines.append("")
        lines.append(
            "If a more accurate identification is required,"
        )
        lines.append(
            "it is recommended to consult with an expert."
        )

    # ── Scenario 4: Uncertain (≤29%) ────────────────────────────────
    elif scenario == 'uncertain':
        lines.append(
            "FAMILY:  Uncertain — confidence too low"
            " to suggest a family"
        )
        lines.append("")
        lines.append(
            "GENUS:   Cannot be determined from this image."
        )
        lines.append("")
        lines.append("This typically happens when:")
        lines.append(
            "  — The fossil is too small in the frame"
        )
        lines.append(
            "  — Lighting is poor or shadows obscure details"
        )
        lines.append(
            "  — The photo is blurry or at a steep angle"
        )
        lines.append("")
        lines.append("For best results:")
        lines.append(
            "  — Crop the photo so the fossil fills"
            " most of the frame"
        )
        lines.append(
            "  — Photograph from directly above"
        )
        lines.append(
            "  — Use even lighting with no shadows"
            " across the ribs"
        )

    # ── Scenarios 5, 6, 7: Non-ammonite ────────────────────────────
    elif scenario == 'non_ammonite':
        non_am_cat = result['non_am_category']

        if non_am_cat == 'Not_Fossil':
            lines.append(
                "FAMILY:  No ammonite detected"
            )
            lines.append("")
            lines.append(
                "This appears to be "
                + result['non_am_display'] + "."
            )
            lines.append("")
            lines.append("For best results:")
            lines.append(
                "  — Crop the photo so the fossil fills"
                " most of the frame"
            )
            lines.append(
                "  — Make sure the specimen is well lit"
                " with no strong shadows"
            )
            lines.append(
                "  — Photograph from directly above"
            )

        else:
            lines.append(
                "FAMILY:  Other fossil type detected"
            )
            lines.append(
                "         (not an ammonite)"
            )
            lines.append("")

            if result['top_non_am_score'] > 60:
                lines.append(
                    "This appears to be "
                    + result['non_am_display'] + "."
                )
            else:
                lines.append(
                    "This resembles another fossil type"
                    " but the image is not clear enough"
                    " to determine which."
                )

            lines.append("")
            lines.append(
                "If a more accurate identification"
                " is required, it is recommended"
                " to consult with an expert."
            )

    return '\n'.join(lines)
