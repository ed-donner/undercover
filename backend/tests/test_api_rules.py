from fastapi.routing import APIRoute

from backend.main import app


def test_every_operation_id_is_its_function_name():
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert routes
    for route in routes:
        assert route.operation_id == route.name


def test_every_operation_has_a_one_line_docstring_and_only_required_inputs():
    schema = app.openapi()
    for operations in schema["paths"].values():
        for operation in operations.values():
            assert operation["operationId"]
            assert operation["description"]
            assert "\n" not in operation["description"].strip()
            for parameter in operation.get("parameters", []):
                assert parameter["required"], operation["operationId"]
            if "requestBody" in operation:
                assert operation["requestBody"]["required"]
                content = operation["requestBody"]["content"]["application/json"]
                name = content["schema"]["$ref"].split("/")[-1]
                body = schema["components"]["schemas"][name]
                assert set(body["required"]) == set(body["properties"]), name
