from app import page_context


def test_get_page_default_none():
    assert page_context.get_page() is None


def test_set_and_reset_page():
    token = page_context.set_page("T", "https://e.test", "<p>x</p>")
    page = page_context.get_page()
    assert page.title == "T"
    assert page.url == "https://e.test"
    assert page.html == "<p>x</p>"
    page_context.reset_page(token)
    assert page_context.get_page() is None
