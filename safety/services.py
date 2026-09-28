from django.core.exceptions import ImproperlyConfigured

from .models import SafetyPolicy

CRISIS_RESOURCE_POLICY_CODE = "default_crisis_resources"


def get_crisis_resources() -> dict:
    policy = SafetyPolicy.objects.filter(
        code=CRISIS_RESOURCE_POLICY_CODE,
        policy_type="resource",
        enabled=True,
    ).first()

    if not policy:
        raise ImproperlyConfigured(f"Safety policy '{CRISIS_RESOURCE_POLICY_CODE}' was not found.")

    if not isinstance(policy.rule_json, dict):
        raise ImproperlyConfigured("Crisis resource policy must contain a JSON object.")

    resources = policy.rule_json.get("resources")
    if not resources:
        raise ImproperlyConfigured("Crisis resource policy does not contain any resources.")

    return policy.rule_json
