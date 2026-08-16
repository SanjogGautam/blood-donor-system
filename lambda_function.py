import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["DONORS_TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
REQUIRED_FIELDS = ["fullName", "bloodGroup", "phone"]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def _response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body_dict, default=str),
    }


def _now():
    return datetime.now(timezone.utc).isoformat()


def list_donors(query_params):
    query_params = query_params or {}
    blood_group = query_params.get("bloodGroup")

    if blood_group:
        result = table.scan(FilterExpression=Attr("bloodGroup").eq(blood_group))
    else:
        result = table.scan()

    items = result.get("Items", [])
    # Handle pagination in case of large tables
    while "LastEvaluatedKey" in result:
        if blood_group:
            result = table.scan(
                FilterExpression=Attr("bloodGroup").eq(blood_group),
                ExclusiveStartKey=result["LastEvaluatedKey"],
            )
        else:
            result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
        items.extend(result.get("Items", []))

    return _response(200, items)


def create_donor(body):
    try:
        data = json.loads(body or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return _response(400, {"error": f"Missing required fields: {', '.join(missing)}"})

    if data["bloodGroup"] not in VALID_BLOOD_GROUPS:
        return _response(400, {"error": f"bloodGroup must be one of {sorted(VALID_BLOOD_GROUPS)}"})

    donor_id = str(uuid.uuid4())
    timestamp = _now()

    item = {
        "donorId": donor_id,
        "fullName": data["fullName"],
        "bloodGroup": data["bloodGroup"],
        "phone": data["phone"],
        "email": data.get("email", ""),
        "donationDate": data.get("donationDate", ""),
        "notes": data.get("notes", ""),
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }

    table.put_item(Item=item)
    return _response(201, item)


def get_donor(donor_id):
    if not donor_id:
        return _response(400, {"error": "donorId is required in the path"})

    result = table.get_item(Key={"donorId": donor_id})
    item = result.get("Item")
    if not item:
        return _response(404, {"error": "Donor not found"})

    return _response(200, item)


def update_donor(donor_id, body):
    if not donor_id:
        return _response(400, {"error": "donorId is required in the path"})

    existing = table.get_item(Key={"donorId": donor_id}).get("Item")
    if not existing:
        return _response(404, {"error": "Donor not found"})

    try:
        data = json.loads(body or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    if "bloodGroup" in data and data["bloodGroup"] not in VALID_BLOOD_GROUPS:
        return _response(400, {"error": f"bloodGroup must be one of {sorted(VALID_BLOOD_GROUPS)}"})

    updatable_fields = ["fullName", "bloodGroup", "phone", "email", "donationDate", "notes"]
    update_expr_parts = []
    expr_values = {}
    expr_names = {}

    for field in updatable_fields:
        if field in data:
            update_expr_parts.append(f"#{field} = :{field}")
            expr_names[f"#{field}"] = field
            expr_values[f":{field}"] = data[field]

    update_expr_parts.append("#updatedAt = :updatedAt")
    expr_names["#updatedAt"] = "updatedAt"
    expr_values[":updatedAt"] = _now()

    table.update_item(
        Key={"donorId": donor_id},
        UpdateExpression="SET " + ", ".join(update_expr_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    updated = table.get_item(Key={"donorId": donor_id}).get("Item")
    return _response(200, updated)


def delete_donor(donor_id):
    if not donor_id:
        return _response(400, {"error": "donorId is required in the path"})

    existing = table.get_item(Key={"donorId": donor_id}).get("Item")
    if not existing:
        return _response(404, {"error": "Donor not found"})

    table.delete_item(Key={"donorId": donor_id})
    return _response(200, {"message": "Donor deleted", "donorId": donor_id})


def lambda_handler(event, context):
    http_method = event.get("httpMethod")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}
    body = event.get("body")
    donor_id = path_params.get("donorId")

    # OPTIONS is normally handled by API Gateway's mock CORS integration,
    # but this is a safety net if it ever routes here.
    if http_method == "OPTIONS":
        return _response(200, {})

    try:
        if http_method == "GET" and donor_id is None:
            return list_donors(query_params)
        elif http_method == "POST" and donor_id is None:
            return create_donor(body)
        elif http_method == "GET" and donor_id is not None:
            return get_donor(donor_id)
        elif http_method == "PUT" and donor_id is not None:
            return update_donor(donor_id, body)
        elif http_method == "DELETE" and donor_id is not None:
            return delete_donor(donor_id)
        else:
            return _response(405, {"error": f"Method {http_method} not allowed on this path"})
    except Exception as e:
        # In production, log this to CloudWatch with more context.
        print(f"ERROR: {str(e)}")
        return _response(500, {"error": "Internal server error", "detail": str(e)})