IaaS Template list
------------------

To get a list of available templates, run GET against */api/iaas-templates/* as authenticated user.

A user with staff role will be able to see all of the templates, non-staff user only active ones.

An optional filter **?cloud=<CLOUD_UUID>** can be used - if defined, only templates that can be instantiated
on a defined cloud are shown.


Create a new template
---------------------

A new template can only be created by users with staff privilege (is_staff=True). Example of a valid request:

.. code-block:: http

    POST /api/iaas-templates/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "CentOS 7 minimal",
        "description": "Minimal installation of CentOS7",
        "icon_url": "http://centos.org/images/logo_small.png",
        "os": "CentOS 7",
        "is_active": true,
        "setup_fee": "10",
        "monthly_fee": "20",
        "template_licenses": [
            "http://example.com:8000/api/template-licenses/5752a31867dc45aebcceafe82c181870/"
        ]
    }


Deletion of a template
----------------------

Deletion of a template is done through sending a DELETE request to the template instance URI.

Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/iaas-templates/33dfe35ecbeb4df0a119c48c206404e9/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Updating a template
-------------------

Can be done by POSTing a new data to the template instance URI, i.e. **api/template-licenses/<UUID>**.