"""The grading rules themselves, driven by each bundled language config."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest_paths import DEFAULT_CONFIG, ENGLISH_CONFIG, HOOKS_DIR, load_module  # noqa: E402

quality = load_module("recap_quality", HOOKS_DIR / "recap_quality.py")

HE = quality.RecapRules(json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8")))
EN = quality.RecapRules(json.loads(ENGLISH_CONFIG.read_text(encoding="utf-8")))

GOOD_HE = """**במילים פשוטות**

**מה השתנה**
- שיניתי את הבדיקה שרצה בסוף כל תשובה, כך שהיא קוראת את הסיכום עצמו.
- עכשיו היא מוודאת שהסיכום כתוב בשפה פשוטה ושהוא לא מדלג על פרטים חשובים.

**איך בדקתי ומה יצא**
הרצתי 12 בדיקות אוטומטיות, וכולן עברו. הן מוודאות שסיכום קצר נעצר ושסיכום טוב עובר בלי הערות.

**מה עוד לא סגור**
ייתכן שהבדיקה תעצור לפעמים סיכום תקין. אם זה יקרה, נרכך אותה אחרי שנראה כמה פעמים זה קרה.

**מה להחליט**
צריך להחליט אם הרף מתאים לך. אפשר גם לחכות שבוע של שימוש ואז להחליט אם לרכך אותו."""

GOOD_EN = """**In plain words**

**What changed**
- I changed the check that runs at the end of every answer, so it reads the summary itself.
- It now makes sure the summary is written plainly and does not skip important details.

**How I checked it**
I ran 12 automated tests, and all of them passed. They make sure a short summary is stopped and a good one goes through.

**What's still open**
The check may sometimes stop a summary that was fine. If that happens, we can relax it after we see how often.

**What to decide**
You need to decide whether the bar feels right. You could also wait a week of real use and decide then."""


def _replace_part(recap: str, part: str, text: str) -> str:
    """The recap with one part's body swapped for `text`."""
    return re.sub(rf"(\*\*{re.escape(part)}\*\*\n).*?(?=\n\n|\Z)",
                  lambda m: m.group(1) + text, recap, count=1, flags=re.DOTALL)


def he(part: str, text: str) -> str:
    return _replace_part(GOOD_HE, part, text)


def en(part: str, text: str) -> str:
    return _replace_part(GOOD_EN, part, text)


def swap_bodies(headings_from: str, bodies_from: str) -> str:
    """Keep one recap's title and headings, fill them with the other's text."""
    blocks = [
        heading_block.split("\n", 1)[0] + "\n" + body_block.split("\n", 1)[1]
        for heading_block, body_block in zip(headings_from.split("\n\n")[1:],
                                             bodies_from.split("\n\n")[1:])
    ]
    return "\n\n".join([headings_from.split("\n\n")[0], *blocks])


def problems(rules, recap: str, body: str = "", changed: int = 1) -> str:
    return "\n".join(rules.diagnose(rules.section(recap), body, changed))


class HebrewStructureTests(unittest.TestCase):
    def test_good_recap_passes(self) -> None:
        self.assertEqual(HE.diagnose(HE.section(GOOD_HE)), [])

    def test_no_title_yields_no_section(self) -> None:
        self.assertEqual(HE.section("סתם טקסט בלי כותרת סיכום."), "")

    def test_unbolded_headings_are_flagged(self) -> None:
        self.assertIn("not bold", problems(HE, GOOD_HE.replace("**מה", "מה").replace("**\n", "\n")))

    def test_missing_part_is_named(self) -> None:
        text = problems(HE, GOOD_HE.split("**מה להחליט**")[0])
        self.assertIn("missing its required headings", text)
        self.assertIn("מה להחליט", text)

    def test_stub_part_is_flagged(self) -> None:
        self.assertIn("almost nothing under them", problems(HE, he("מה להחליט", "כלום.")))

    def test_more_changed_files_need_a_longer_recap(self) -> None:
        self.assertEqual(problems(HE, GOOD_HE, changed=1), "")
        self.assertIn("too short", problems(HE, GOOD_HE, changed=8))


class HebrewPlainLanguageTests(unittest.TestCase):
    def test_wrong_language_is_flagged(self) -> None:
        # The realistic failure: Hebrew headings, English body.
        self.assertIn("not actually written in Hebrew", problems(HE, swap_bodies(GOOD_HE, GOOD_EN)))

    def test_unexplained_jargon_gets_a_plain_suggestion(self) -> None:
        text = problems(HE, he("מה השתנה", "- תיקנתי את הבאג בכפתור ועשיתי commit לשינוי.\n"
                                            "- עכשיו הכפתור מגיב גם בטלפון."))
        for expected in ("commit", "שמירת גרסה", "באג", "תקלה"):
            self.assertIn(expected, text)

    def test_jargon_explained_in_brackets_or_quoted_is_fine(self) -> None:
        for line in ("- תיקנתי את התקלה ועשיתי commit (שמירת גרסה) לשינוי.",
                     "- תיקנתי את התקלה ושמרתי גרסה חדשה (commit) של השינוי.",
                     '- המילים "הוק" ו"סקריפט" נעצרו הכי הרבה בבדיקה.'):
            self.assertEqual(HE.unexplained_jargon(line), [], line)

    def test_prefixes_match_but_unrelated_words_do_not(self) -> None:
        for phrase in ("עשיתי ה-commit", "שמרתי בקומיט", "ההוק רץ", "מצאתי באג"):
            self.assertTrue(HE.unexplained_jargon(phrase), phrase)
        for phrase in ("המקום הוקם מזמן", "זה רחוק מכאן", "a commitment to quality", "הדבר באג'נדה"):
            self.assertEqual(HE.unexplained_jargon(phrase), [], phrase)

    def test_long_sentence_is_flagged(self) -> None:
        long_one = ("שיניתי את הבדיקה שרצה בסוף כל תשובה כך שהיא קוראת את הסיכום עצמו ובודקת "
                    "שהוא כתוב בשפה פשוטה ושהוא לא מדלג על אף פרט חשוב שהופיע בהודעה הארוכה "
                    "שכתבתי לפניו ושהוא מסביר כל מילה מקצועית.")
        self.assertIn("too long to read easily", problems(HE, he("מה השתנה", long_one + " זה הכול.")))

    def test_wall_of_file_names_is_flagged(self) -> None:
        wall = ("- עדכנתי את `a.py`, `b.py`, `c.py` ואת `d.py`.\n"
                "- וגם את ~/x/e.json, את ~/x/f.json ואת ~/x/g.json.")
        self.assertIn("raw paths", problems(HE, he("מה השתנה", wall)))


class HebrewCompletenessTests(unittest.TestCase):
    def test_dropped_test_numbers_are_flagged(self) -> None:
        self.assertIn("42", problems(HE, GOOD_HE, "הרצתי את כל הבדיקות: 42/42 עברו אחרי התיקון."))

    def test_task_numbers_are_not_test_results(self) -> None:
        body = "Tasks 4–5 passed review and are clean. Task 8 passed review with one gap."
        self.assertEqual(problems(HE, GOOD_HE, body), "")

    def test_hidden_failures_are_flagged(self) -> None:
        body = "הרצתי את הבדיקות. 3 בדיקות נכשלו בגלל שינוי במסך הכניסה."
        recap = he("איך בדקתי ומה יצא", "הרצתי 3 בדיקות. הן מוודאות שמסך הכניסה נפתח ושסיסמה שגויה נדחית.")
        self.assertIn("failed or was not checked", problems(HE, recap, body))

    def test_zero_failures_and_described_failures_are_not_reports(self) -> None:
        for body in ("הרצתי את הבדיקות: 12 עברו ו-0 נכשלו. אף בדיקה לא נכשלה.",
                     "אם הרצה נכשלת, ההרצה הבאה מתחילה מהנקודה האחרונה."):
            self.assertEqual(problems(HE, GOOD_HE, body), "", body)

    def test_unexplained_check_is_flagged(self) -> None:
        recap = he("איך בדקתי ומה יצא", "הרצתי 12 בדיקות וכל הבדיקות עברו בהצלחה. הכול עובד כמו שצריך.")
        self.assertIn("what was actually checked", problems(HE, recap))

    def test_hands_on_check_or_honest_no_check_is_fine(self) -> None:
        for text in ("פתחתי את האתר בטלפון ולחצתי על הכפתור החדש. הוא הגיב מיד והטופס נשלח.",
                     "לא בדקתי את השינוי, כי אין לי גישה לטלפון. צריך לפתוח את האתר ולנסות."):
            self.assertEqual(problems(HE, he("איך בדקתי ומה יצא", text)), "", text)

    def test_many_changed_files_need_several_lines(self) -> None:
        recap = he("מה השתנה", "שיניתי כמה דברים בקוד כדי שהכול יעבוד טוב יותר ויהיה מסודר.")
        self.assertIn("6 files", problems(HE, recap, changed=6))


class EnglishConfigTests(unittest.TestCase):
    """The same engine, driven by the English config."""

    def test_english_recap_passes(self) -> None:
        self.assertEqual(EN.diagnose(EN.section(GOOD_EN)), [])

    def test_english_config_rejects_hebrew_recap(self) -> None:
        self.assertIn("not actually written in English", problems(EN, swap_bodies(GOOD_EN, GOOD_HE)))

    def test_english_jargon_and_checks(self) -> None:
        self.assertIn("put it live", problems(EN, en("What changed",
            "- I fixed the login button and deployed it to the site.\n- It now works on phones.")))
        self.assertIn("what was actually checked", problems(EN, en("How I checked it",
            "I ran 12 tests and all the tests passed. Everything works as it should.")))
        self.assertEqual(problems(EN, en("How I checked it",
            "I opened the site on my phone and clicked the new button. It responded at once.")), "")

    def test_english_completeness(self) -> None:
        self.assertIn("179", problems(EN, GOOD_EN, "The code is finished: 179 tests pass."))
        self.assertIn("failed or was not checked",
                      problems(EN, GOOD_EN, "Two runs later, 3 tests failed on the login screen."))
        self.assertEqual(problems(EN, GOOD_EN, "Task 8 passed review. 12 passed, 0 failed."), "")

    def test_spec_text_follows_the_config(self) -> None:
        self.assertIn("What changed", EN.spec)
        self.assertIn("מה השתנה", HE.spec)


if __name__ == "__main__":
    unittest.main()
