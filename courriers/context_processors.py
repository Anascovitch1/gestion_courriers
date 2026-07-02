def notifications(request):
    if request.user.is_authenticated:
        qs = request.user.notifications.filter(lu=False)
        return {"notifs_non_lues": qs.count(), "notifs_recentes": qs[:8]}
    return {"notifs_non_lues": 0, "notifs_recentes": []}
