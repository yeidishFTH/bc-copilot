from app.services.actions.detector import (
    ActionDetector,
)


def test_publish_knowledge_detected():

    detector = ActionDetector()

    result = detector.detect(
        "תעלה את נוהל KYC לוויקי"
    )

    assert result is not None
    assert result.action == "publish_knowledge"
    assert result.requires_approval is True


def test_regular_question_is_not_action():

    detector = ActionDetector()

    result = detector.detect(
        "תסכם לי את נוהל מחיקת לקוח"
    )

    assert result is None


def test_wiki_information_question_is_not_action():

    detector = ActionDetector()

    result = detector.detect(
        "מה כתוב בנוהל פרסום לוויקי"
    )

    assert result is None
