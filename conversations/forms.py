from django import forms


class ChatMessageForm(forms.Form):
    content = forms.CharField(
        label="",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Write your message here...",
            }
        ),
    )
