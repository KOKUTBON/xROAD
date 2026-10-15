"""Apply deployment module settings before any disabled workflow can run."""

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from road_risk_modeling.institutional_product import module_for_api_path


class InstitutionModulesMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled_modules: tuple[str, ...],
        jurisdictions: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled_modules = frozenset(enabled_modules)
        self.jurisdictions = (
            frozenset(jurisdictions) if jurisdictions is not None else None
        )

    async def dispatch(self, request, call_next):
        city = re.match(r"^/v1/[^/]+/cities/([^/]+)(?:/|$)", request.url.path)
        if (
            city
            and self.jurisdictions is not None
            and city.group(1) not in self.jurisdictions
        ):
            return JSONResponse(
                {"detail": "Jurisdiction is not configured for this institution."},
                status_code=404,
            )
        if (
            request.url.path.startswith("/v1/public/cities")
            and "public_portal" not in self.enabled_modules
        ):
            return JSONResponse(
                {"detail": "Public transparency is not enabled for this institution."},
                status_code=404,
            )
        module = module_for_api_path(request.url.path)
        if module and module not in self.enabled_modules:
            return JSONResponse(
                {
                    "detail": "This module is not enabled for this institution.",
                    "code": "institution_module_disabled",
                    "module": module,
                },
                status_code=404,
            )
        return await call_next(request)
