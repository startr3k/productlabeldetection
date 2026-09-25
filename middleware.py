# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from functools import wraps
from typing import Any, Callable, Dict

import firebase_admin
from firebase_admin import auth  # noqa: F401
from flask import g, request, Response
import structlog


default_app = firebase_admin.initialize_app()

# [START cloudrun_user_auth_jwt]
def jwt_authenticated(func: Callable[..., int]) -> Callable[..., int]:
    @wraps(func)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        header = request.headers.get("Authorization", None)
        if not header:
            return Response(status=401)

        parts = header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            return Response(status=400, response="Malformed Authorization header")

        try:
            decoded_token = firebase_admin.auth.verify_id_token(parts[1])
        except Exception as e:
            logger.exception(e)
            # Log the detail but never echo the exception back to the caller.
            return Response(status=403, response="Invalid or expired token")

        user = firebase_admin.auth.get_user(decoded_token["uid"])

        # Identity is stored on the request context so concurrent requests cannot
        # observe each other's user. It is always derived from the verified
        # token, never from client-supplied values.
        g.uid = decoded_token["uid"]
        g.email = user.email or ""
        g.display_name = user.display_name or g.email

        # Kept for backwards compatibility with existing handlers.
        request.uid = g.uid

        return func(*args, **kwargs)

    return decorated_function


# [END cloudrun_user_auth_jwt]

# adapted from https://github.com/ymotongpoo/cloud-logging-configurations/blob/master/python/structlog/main.py


def field_name_modifier(
    logger: structlog._loggers.PrintLogger, log_method: str, event_dict: Dict
) -> Dict:
    # Changes the keys for some of the fields, to match Cloud Logging's expectations
    event_dict["severity"] = event_dict["level"]
    del event_dict["level"]
    event_dict["message"] = event_dict["event"]
    del event_dict["event"]
    return event_dict


def getJSONLogger() -> structlog._config.BoundLoggerLazyProxy:
    # extend using https://www.structlog.org/en/stable/processors.html
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            field_name_modifier,
            structlog.processors.TimeStamper("iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    return structlog.get_logger()


logger = getJSONLogger()


def logging_flush() -> None:
    # Setting PYTHONUNBUFFERED in Dockerfile ensured no buffering
    pass

def getDisplayName() -> str:
    # Request-scoped: reads the identity the decorator stored on flask.g.
    # Deliberately does not log the user's name or email.
    return getattr(g, "display_name", "")
