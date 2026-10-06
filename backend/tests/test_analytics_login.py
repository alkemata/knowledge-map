from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException

from app.api import analytics_dashboard
from app.models import Role, User


def test_dashboard_redirects_signed_out_user_to_login_and_back():
    response = analytics_dashboard(days=30, db=None, actor=None)
    assert response.status_code == 303
    location = urlsplit(response.headers["location"])
    assert location.path == "/api/v1/auth/oidc/start"
    assert parse_qs(location.query)["next"] == ["/api/v1/analytics/dashboard?days=30"]


def test_dashboard_does_not_redirect_signed_in_non_admin():
    reader = User(display_name="Reader", role=Role.reader)
    with pytest.raises(HTTPException) as error:
        analytics_dashboard(days=7, db=None, actor=reader)
    assert error.value.status_code == 403
