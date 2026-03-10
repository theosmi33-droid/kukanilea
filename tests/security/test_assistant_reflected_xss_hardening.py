from __future__ import annotations


def test_assistant_escapes_query_params_in_search_form(admin_client):
    _app, client = admin_client
    payload = '"><script>alert(1)</script>'

    response = client.get("/assistant", query_string={"q": payload, "kdnr": payload})

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert payload not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
