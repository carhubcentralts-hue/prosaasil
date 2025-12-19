def test_compact_instructions_are_business_only_and_capped():
    """
    Regression test: COMPACT (session.update.instructions) must be business-only.
    It must not include global/system wording like "professional phone agent".
    """
    from server.services.realtime_prompt_builder import build_compact_business_instructions, COMPACT_GREETING_MAX_CHARS

    business_prompt = (
        "שלום, הגעתם ל{{business_name}}. מטרת השיחה: לקבוע תור. "
        "פתח/י בזהות העסק ואז שאל/י מה השירות המבוקש."
        "\n\nפרטים נוספים: " + ("א" * 2000)
    ).replace("{{business_name}}", "בדיקה בע״מ")

    compact = build_compact_business_instructions(business_prompt)

    assert compact
    assert len(compact) <= COMPACT_GREETING_MAX_CHARS
    assert "professional phone agent" not in compact.lower()
    assert "isolation:" not in compact.lower()
    assert "turn-taking" not in compact.lower()

