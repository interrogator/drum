from django.forms.models import modelform_factory
from django.forms import ValidationError
from django import forms
from django.conf import settings
from drum.chambers.models import Chamber

AUTOMOD_CHOICES = [(None, 'None')]
AUTOMOD_CHOICES += [(k, v) for k, v in settings.EVALUATORS.items()]

# labels to display
balance_labels = {"min_thread_balance": "Minimum balance to create thread",
                  "min_comment_balance": "Minimum balance to comment",
                  "automod_can_fine": "Can automoderators fine users?",
                  "max_fine": "Maximum fine amount"}

# formatting field names and other junk
mod_and_sev = list()
mods = list()
for char in 'abcde':
    mod, sev = "automod_{}".format(char), "severity_{}".format(char)
    mods.append(mod)
    mod_and_sev.append(mod)
    mod_and_sev.append(sev)
    balance_labels[mod] = "Add automoderator"
    balance_labels[sev] = "Automoderator severity"

fields = ["chamber", "description"] + list(balance_labels) + mod_and_sev
widgets = {name: forms.Select(choices=AUTOMOD_CHOICES) for name in mods}

widgets['balance'] = forms.HiddenInput()
kwargs = dict(fields=fields, widgets=widgets, labels=balance_labels)
BaseChamberForm = modelform_factory(Chamber, **kwargs)


class ChamberForm(BaseChamberForm):

    def clean(self):
        link = self.cleaned_data.get("link")
        description = self.cleaned_data.get("description")
        if not link and not description:
            raise ValidationError("Either a link or description is required")
        return self.cleaned_data
