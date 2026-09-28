from django.urls import path

from .views import (
    ConversationCloseView,
    ConversationDetailView,
    ConversationHistoryView,
    ConversationHubView,
    ConversationSendMessageView,
)

app_name = "conversations"

urlpatterns = [
    path("", ConversationHubView.as_view(), name="hub"),
    path("history/", ConversationHistoryView.as_view(), name="history"),
    path("<int:pk>/", ConversationDetailView.as_view(), name="detail"),
    path("<int:pk>/send/", ConversationSendMessageView.as_view(), name="send"),
    path("<int:pk>/close/", ConversationCloseView.as_view(), name="close"),
]
