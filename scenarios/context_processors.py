from scenarios.dealing import SESSION_KEY, deal_is_active


def role_deal(request):
    return {"role_deal_active": deal_is_active(request.session.get(SESSION_KEY))}
