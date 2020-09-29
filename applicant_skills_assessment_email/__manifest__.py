# Author: Lanto RAZAFINDRABE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'Applicant skills assessment email',
    'version': '13.0.1.0.0',
    'sequence': 1,
    'summary': """Prepare test case documents and send it by email to applicants""",
    'description': """This module allows you to prepare a list of requirements for applicants and send it
    by email as attachment.""",
    'category': 'Human Resources',
    'author': 'Lanto Razafindrabe <farinoire@gmail.com>',
    'depends': ['hr_recruitment'],
    'data': [
        "security/ir.model.access.csv",
        "data/mail_data.xml",
        "views/assessment_view.xml",
        "report/views/applicant_requirement_report_view.xml",
        "report/templates/report_applicant_requirement.xml",
    ],
    'license': "AGPL-3",
    'qweb': [],
    'demo': [],
    'installable': True,
    'application': False,
}
