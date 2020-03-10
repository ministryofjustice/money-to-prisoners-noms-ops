from django.test import SimpleTestCase
from settings.forms import JobInformationForm


class JobInformationFormTestCase(SimpleTestCase):
    def test_form_returns_error_when_no_other_job_title_given(self):
        """Test that a form is not valid if no job title given when Other is selected"""

        form = JobInformationForm({
            'job_title': 'Other',
            'prison_estate': 'Regional',
            'tasks': 'Some tasks',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('Please enter your job title', form['other_title'].errors)

    def test_form_returns_job_title_or_other_in_cleaned_data_when_other_selected(self):
        form = JobInformationForm({
            'job_title': 'Other',
            'prison_estate': 'Regional',
            'tasks': 'Some tasks',
            'other_title': 'The Gaffer'
        })

        self.assertTrue(form.is_valid())
        self.assertDictContainsSubset({'job_title_or_other': 'The Gaffer'}, form.cleaned_data)

    def test_form_returns_job_title_or_other_in_cleaned_data_if_other_not_selected(self):
        form = JobInformationForm({
            'job_title': 'Intelligence officer',
            'prison_estate': 'Regional',
            'tasks': 'Some tasks',
            'other_title': 'The Real Deal'
        })

        self.assertTrue(form.is_valid())
        self.assertDictContainsSubset({'job_title_or_other': 'Intelligence officer'}, form.cleaned_data)

    def test_form_invalid_with_no_data(self):
        form = JobInformationForm({
            'job_title': '',
            'prison_estate': '',
            'tasks': '',
            'other_title': ''
        })

        self.assertFalse(form.is_valid())
