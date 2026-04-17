from django import forms
from .models import Question, Answer, CustomUser, Quiz
from django.contrib.auth.models import User

class UserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username')

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class QuizForm(forms.Form):
    def __init__(self, *args, **kwargs):
        quiz_id = kwargs.pop('quiz_id', None)
        super(QuizForm, self).__init__(*args, **kwargs)
        if quiz_id:
            questions = Question.objects.filter(quiz=quiz_id)
            for question in questions:
                self.fields[f'question_{question.id}'] = forms.ModelChoiceField(
                    queryset=Answer.objects.filter(question=question),
                    empty_label="Выберите ответ",
                    label=question.text
                )