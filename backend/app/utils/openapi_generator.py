"""
OpenAPI 3.1 schema generator and documentation.
Automatically generates comprehensive API documentation from FastAPI application.
"""

from fastapi import FastAPI
from typing import Dict, List, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class OpenAPIDocumentationGenerator:
    """
    Generates comprehensive OpenAPI 3.1 documentation.
    
    Features:
    - Automatic endpoint discovery
    - Request/response examples
    - Security schemes documentation
    - Rate limiting documentation
    - WebSocket endpoints
    - Error responses documentation
    """
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.routes = app.routes
        self.base_schema = {
            "openapi": "3.1.0",
            "info": {
                "title": "Virtual World Exchange API",
                "version": "1.0.0",
                "description": "Comprehensive trading exchange platform API",
                "contact": {
                    "name": "API Support",
                    "email": "support@example.com"
                },
                "license": {
                    "name": "MIT"
                }
            },
            "servers": [
                {
                    "url": "http://localhost:8000",
                    "description": "Development server"
                },
                {
                    "url": "https://api.example.com",
                    "description": "Production server"
                }
            ]
        }
    
    def generate_schema(self) -> Dict[str, Any]:
        """Generate complete OpenAPI schema."""
        schema = self.base_schema.copy()
        
        # Add paths
        schema["paths"] = self._generate_paths()
        
        # Add components
        schema["components"] = self._generate_components()
        
        # Add tags
        schema["tags"] = self._generate_tags()
        
        return schema
    
    def _generate_paths(self) -> Dict[str, Dict[str, Any]]:
        """Generate paths section from FastAPI routes."""
        paths = {}
        
        for route in self.routes:
            if not hasattr(route, "path") or not hasattr(route, "methods"):
                continue
            
            path = route.path
            if path not in paths:
                paths[path] = {}
            
            for method in route.methods:
                method_lower = method.lower()
                if method_lower == "head":
                    continue
                
                operation = self._generate_operation(route, method_lower)
                if operation:
                    paths[path][method_lower] = operation
        
        return paths
    
    def _generate_operation(self, route, method: str) -> Optional[Dict[str, Any]]:
        """Generate operation object for a route method."""
        operation = {
            "summary": self._get_summary(route),
            "description": self._get_description(route),
            "tags": self._get_tags(route),
            "parameters": self._generate_parameters(route),
            "responses": self._generate_responses(route, method),
        }
        
        # Add request body for POST/PUT/PATCH
        if method in ["post", "put", "patch"]:
            request_body = self._generate_request_body(route)
            if request_body:
                operation["requestBody"] = request_body
        
        # Add security
        operation["security"] = self._generate_security(route)
        
        return operation
    
    def _get_summary(self, route) -> str:
        """Extract summary from route."""
        if hasattr(route, "summary") and route.summary:
            return route.summary
        
        path = getattr(route, "path", "")
        method = list(getattr(route, "methods", []))[0].lower()
        return f"{method.upper()} {path}"
    
    def _get_description(self, route) -> str:
        """Extract description from route docstring."""
        if hasattr(route, "description") and route.description:
            return route.description
        
        if hasattr(route, "endpoint"):
            docstring = route.endpoint.__doc__
            if docstring:
                return docstring.strip()
        
        return ""
    
    def _get_tags(self, route) -> List[str]:
        """Extract tags from route."""
        if hasattr(route, "tags"):
            return list(route.tags) if route.tags else []
        
        path = getattr(route, "path", "")
        parts = path.strip("/").split("/")
        if parts and parts[0] != "api":
            return [parts[0]]
        
        return []
    
    def _generate_parameters(self, route) -> List[Dict[str, Any]]:
        """Generate parameters section."""
        parameters = []
        path = getattr(route, "path", "")
        
        # Extract path parameters
        import re
        path_params = re.findall(r"{(\w+)}", path)
        for param in path_params:
            parameters.append({
                "name": param,
                "in": "path",
                "required": True,
                "schema": {
                    "type": "string"
                }
            })
        
        # Query parameters (if documented in endpoint)
        if hasattr(route, "query_params"):
            for param_name, param_info in route.query_params.items():
                parameters.append({
                    "name": param_name,
                    "in": "query",
                    "required": param_info.get("required", False),
                    "schema": {
                        "type": param_info.get("type", "string")
                    },
                    "description": param_info.get("description", "")
                })
        
        return parameters
    
    def _generate_request_body(self, route) -> Optional[Dict[str, Any]]:
        """Generate request body schema."""
        request_body = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/RequestPayload"
                    },
                    "examples": {
                        "default": {
                            "value": self._get_example_request(route)
                        }
                    }
                }
            }
        }
        return request_body
    
    def _generate_responses(self, route, method: str) -> Dict[str, Any]:
        """Generate responses section."""
        responses = {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/SuccessResponse"
                        },
                        "examples": {
                            "default": {
                                "value": self._get_example_response(route, method)
                            }
                        }
                    }
                }
            },
            "400": {
                "description": "Bad request",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ErrorResponse"
                        }
                    }
                }
            },
            "401": {
                "description": "Unauthorized",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ErrorResponse"
                        }
                    }
                }
            },
            "403": {
                "description": "Forbidden",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ErrorResponse"
                        }
                    }
                }
            },
            "429": {
                "description": "Rate limit exceeded",
                "headers": {
                    "Retry-After": {
                        "schema": {
                            "type": "integer"
                        },
                        "description": "Seconds to retry after"
                    },
                    "X-RateLimit-Limit": {
                        "schema": {
                            "type": "integer"
                        },
                        "description": "Rate limit cap"
                    },
                    "X-RateLimit-Remaining": {
                        "schema": {
                            "type": "integer"
                        },
                        "description": "Remaining requests"
                    },
                    "X-RateLimit-Reset": {
                        "schema": {
                            "type": "integer"
                        },
                        "description": "Epoch timestamp to reset"
                    }
                }
            },
            "500": {
                "description": "Internal server error",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ErrorResponse"
                        }
                    }
                }
            }
        }
        return responses
    
    def _generate_security(self, route) -> List[Dict[str, List[str]]]:
        """Generate security requirements."""
        # Check if route requires authentication
        if any(dep for dep in getattr(route, "dependencies", []) 
               if "current_user" in str(dep)):
            return [{"BearerAuth": []}]
        return []
    
    def _generate_components(self) -> Dict[str, Any]:
        """Generate components section with schemas and security schemes."""
        return {
            "schemas": {
                "SuccessResponse": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "example": "success"
                        },
                        "data": {
                            "type": "object"
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time"
                        }
                    }
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "example": "error"
                        },
                        "error": {
                            "type": "string"
                        },
                        "detail": {
                            "type": "string"
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time"
                        }
                    }
                },
                "RequestPayload": {
                    "type": "object",
                    "additionalProperties": {}
                },
                "Order": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string"
                        },
                        "symbol": {
                            "type": "string"
                        },
                        "side": {
                            "type": "string",
                            "enum": ["BUY", "SELL"]
                        },
                        "quantity": {
                            "type": "number"
                        },
                        "price": {
                            "type": "number"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["PENDING", "OPEN", "PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED"]
                        },
                        "created_at": {
                            "type": "string",
                            "format": "date-time"
                        }
                    }
                },
                "Trade": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string"
                        },
                        "symbol": {
                            "type": "string"
                        },
                        "price": {
                            "type": "number"
                        },
                        "quantity": {
                            "type": "number"
                        },
                        "side": {
                            "type": "string",
                            "enum": ["BUY", "SELL"]
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time"
                        }
                    }
                },
                "MarketData": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string"
                        },
                        "bid": {
                            "type": "number"
                        },
                        "ask": {
                            "type": "number"
                        },
                        "last_trade": {
                            "type": "number"
                        },
                        "bid_volume": {
                            "type": "number"
                        },
                        "ask_volume": {
                            "type": "number"
                        }
                    }
                }
            },
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT Bearer token for authentication"
                },
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key for service-to-service authentication"
                }
            }
        }
    
    def _generate_tags(self) -> List[Dict[str, str]]:
        """Generate tags section."""
        tags_set = set()
        for route in self.routes:
            if hasattr(route, "tags"):
                tags_set.update(route.tags or [])
        
        return [
            {
                "name": tag,
                "description": f"{tag} operations"
            }
            for tag in sorted(tags_set)
        ]
    
    def _get_example_request(self, route) -> Dict[str, Any]:
        """Get example request body."""
        return {
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.50,
            "side": "BUY"
        }
    
    def _get_example_response(self, route, method: str) -> Dict[str, Any]:
        """Get example response body."""
        return {
            "status": "success",
            "data": {
                "id": "order_123",
                "symbol": "AAPL",
                "quantity": 100,
                "price": 150.50,
                "side": "BUY",
                "status": "OPEN"
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }


def generate_openapi_docs(app: FastAPI) -> Dict[str, Any]:
    """
    Generate OpenAPI documentation for FastAPI app.
    
    Args:
        app: FastAPI application
    
    Returns:
        OpenAPI 3.1 schema dictionary
    """
    generator = OpenAPIDocumentationGenerator(app)
    return generator.generate_schema()


def save_openapi_schema(app: FastAPI, filepath: str) -> None:
    """
    Generate and save OpenAPI schema to JSON file.
    
    Args:
        app: FastAPI application
        filepath: Path to save OpenAPI schema JSON
    """
    schema = generate_openapi_docs(app)
    with open(filepath, "w") as f:
        json.dump(schema, f, indent=2)
    logger.info(f"OpenAPI schema saved to {filepath}")


# OpenAPI schema validation constants

REQUIRED_FIELDS = {
    "openapi",
    "info",
    "paths",
    "components"
}

MINIMUM_INFO_FIELDS = {
    "title",
    "version"
}

RESPONSE_CODES = {
    "200": "Success",
    "201": "Created",
    "400": "Bad Request",
    "401": "Unauthorized",
    "403": "Forbidden",
    "404": "Not Found",
    "429": "Too Many Requests",
    "500": "Internal Server Error"
}

# OpenAPI documentation examples

EXAMPLE_SECURITY_SCHEME = {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT"
}

EXAMPLE_RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit": {
        "schema": {"type": "integer"},
        "description": "Requests allowed per window"
    },
    "X-RateLimit-Remaining": {
        "schema": {"type": "integer"},
        "description": "Requests remaining"
    },
    "X-RateLimit-Reset": {
        "schema": {"type": "integer"},
        "description": "Unix timestamp to reset"
    }
}

EXAMPLE_ERROR_RESPONSE = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "example": "error"
        },
        "error": {
            "type": "string",
            "example": "INVALID_REQUEST"
        },
        "detail": {
            "type": "string",
            "example": "Missing required field: symbol"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time"
        },
        "request_id": {
            "type": "string",
            "description": "Unique request identifier for debugging"
        }
    }
}
