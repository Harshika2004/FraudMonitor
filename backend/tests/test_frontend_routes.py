def test_frontend_pages_serve_html(client):
    pages = ["/", "/transactions", "/alerts", "/rules", "/customers"]
    for path in pages:
        res = client.get(path)
        assert res.status_code == 200
        assert "FraudMonitor" in res.text

def test_static_files_served(client):
    res_css = client.get("/static/css/style.css")
    assert res_css.status_code == 200
    assert "Banking Transaction Monitoring" in res_css.text

    res_js = client.get("/static/js/api.js")
    assert res_js.status_code == 200
    assert "ApiClient" in res_js.text
