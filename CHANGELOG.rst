CHANGELOG
=========

Release NEXT
------------
- <none yet>.

Release 0.81.0
--------------
- Refactored template application adding capability to provision multiple resources in a row.

Release 0.80.0
--------------
- Exposed error_message field for each of the SynchronizableMixin-objects.
- Added role manipulation capability to /admin.
- Fixed filtering of the SLA view of IaaS resources.

Release 0.79.0
--------------
- Refactored cost tracking to make it pluggable.
- Refactor plugin system.
- Add events for failing and recovering Link and Service instances.
- Bugfixes.

Release 0.78.0
--------------
- Fix plugin support.
- Documentation updates.
- Bugfixes.

Release 0.77.0
--------------
- Refactor documentation to support plugins.
- Move OpenStack documentation to the plugins section.
- Add documentation section for SugarCRM plugin.
- Make services filtering by customer consistent.
- Fix OpenStack instance provisioning.
- Make admin page application names more user friendly.
- Bugfixes.

Release 0.76.0
--------------
- Bump supported versions of OpenStack libraries to Juno version.
- Implementation of lazy SPL creation for more efficient backend resource usage.
- Introduction of NEW and CREATION_SCHEDULED states for the SPLs.
- Added automatic OpenStack tenant deletion on OpenStack SPL removal.
- Fix maximum length for generated OpenStack and Zabbix names to fit into their model.
- Allow organisation claim to be modified by the claimer before it's confirmed.
- Bugfixes.

Release 0.75.0
--------------
- Multiple bugfixes.
- Added invoice generation.
- Add reporting of shared service consumption to KillBill.
- Enhanced cost esimation module.
- Dropped WHMCS billing, replaced with KillBill.io.
- New admin skin based on Fluent project.

Release 0.74.0
--------------
- Bugfixes.

Release 0.73.0
--------------
- Moved cost_tracking to IaaS.
- External net is now synced on CPM synchronization.
- Improved quotas timeline calculation.
- Improved price estimate computation.
- Improved WHMCS integration for instance lifecycle.
- Bugfixes.

Release 0.72.0
--------------
- Order tracking is now optional and configurable.
- Spaces are now allowed in price list item names.
- Improved Django admin list filtering.
- Dash and underscore are now allowed in a flavor name.
- Added a call to Zabbix registration on CPM sync.
- Added filters for OpenStack services and service-project links.
- Forced non-sudo mode on Travis.
- Changed filter names for the consistency.
- Added customer to filter fields list.
- Added filters for service and service-project link.
- Flavor name is now preserved on instance import.
- Added backup support for order tracking.
- Improved WHMCS integration.
- Improved documentation.

Release 0.71.0
--------------
- Moved to a container based Travis infrastructure.
- Replaced whistles.org with extranet.whistles.org in test data set.
- Max one license of specific type is now allowed.
- Removed IaaS template fees.
- Update versions of OpenStack libraries.
- Fixed Zabbix host and security groups creation on CPM creation.

Release 0.70.0
--------------
- UUID is now exposed for hooks.
- Non-staff user can now create new organizations.
- Fix project deletion.
- Implemented endpoint for price list items.
- Fixed stevedore dependency version.
- Improved price estimate API.
- Added ability to aggregate licenses by customer.
- Fix repository configuration step in install script.
- Added an option to list unmanaged resources.
- Zabbix hosts are now created for PaaS tenants.
- Added price list table endpoint.
- Price list creation and update are now done in one transaction.
- Added Azure service type.
- Instance security groups are now validated on instance provisioning.
- Added plugin settings configuration support.
- Logging improvements.
- Bugfixes.

Release 0.69.0
--------------
- Exact search is now used for username in permissions.
- Added AWS EC2 endpoint with support for import of a new resource.
- Connected services of a project are now exposed in REST API.
- Bugfixes.

Release 0.68.0
--------------
- Quotas are now changed before instance creation.
- Exposed date_joined attribute for user.

Release 0.67.0
--------------
- Enabled filtering service-project-link by project_uuid.
- Enabled filtering resources and backups by project_uuid.
- Added endpoints for price estimate calculation.

Release 0.66.0
--------------
- Proper error handling on SSH key removing.
- Implemented payments via Paypal.
- Fixed SupportedServices auto-discovery.
- Added resource quotas for projects and services.
- Improved resource filtering.
- Bugfixes.

Release 0.65.0
--------------
- Events are now routed from generation to notification according to subscription.
- Implemented historical data for event count.
- Update oslo.config dependency version.
- Implemented REST API for notifications subscription.
- Added external network creation task.
- Documentation improvements.

Release 0.64.0
--------------
- Alert statistics are moved to to alers app.
- Improve OpenStack router detection.
- Zero usage is now returned if usage is not available.
- Moved OpenStackSettings to ServiceSettings.
- Extended existing router detection.
- Remove deprecated OPENSTACK_CREDENTIALS settings.
- Documentation improvements.
- Bugfixes.

Release 0.63.0
--------------
- Added structure templates to mainfest.
- Fixed service settings editing in admin.
- Added merged resources view for all kinds of resources.
- Zabbix query optimizations.
- Added an option to provision JIRA projects.
- Added an option to manage GitLab groups/projects.
- Improved base service classes and add support of syncing users with backend.
- Bugfixes.
- Documentation improvements.

Release 0.62.0
--------------
- Implemented customer annual report generation.
- Added backup storage to invoice calculation.
- Added usage report generation in PDF.
- Implemented customer estimated price endpoint.
- Fix dummy client to work with CLI executions.
- Invoicing improvements.
- Bugfixes.

Release 0.61.0
--------------
- Improve performance of quotas timeline statistics API.
- Improved filters for alerts.
- Optimized query to Zabbix database for timeline stats.
- Fixed instance installation polling.
- Fixed OpenStack session initialization.
- Fixed documentation formatting.
- Fix tests for alerts.

Release 0.60.0
--------------
- Extended invoice generation with licensing data.
- Added ability to cancel alert acknowledgment.
- Added customers admin command for invoices creation.
- Added support for calculating monthly license usage.
- Documentation improvements.
- Test fixes.

Release 0.59.0
--------------
- Instance type is preserved on backup/restoration.
- Host IDs are now queried in Zabbix with a single call.
- UUID is now exposed at service projects list.

Release 0.58.0
--------------
- backup_source is now expoased in backup logging.
- Refactored price list synchronization with backend.
- Project admin and staff can now manage security groups and security group rules.
- Fix keystone session save and recover.
- Track keystone credentials instead of session itself.
- Implemented CPM security groups quotas.
- Logging improvements.
- Documentation improvements.

Release 0.57.0
--------------
- Issue status is now exposed over REST API.

Release 0.56.0
--------------
- Add endpoint for marking alerts as acknowledged.
- REST API for organization logo uploading.
- Added billing templates.
- Customer quotas are shown at customer endpoint.
- ProjectGroup viewset is now respecting user view permissions on project.
- Upgraded pysaml2 and djangosaml2 dependencies.
- Logging improvements.
- Bugfixes.

Release 0.55.1
--------------
- Added project_group field to project logging.

Release 0.55.0
--------------
- Bugfixes.
- Support billing data extraction from nova.

Release 0.54.0
--------------
- Alert API filtering extensions.
- Bugfixes of PaaS instance monitoring polling.

Release 0.53.0
--------------
- Extend alert filtering API.
- Bugfixes.

Release 0.52.0
--------------
- Alert filterting and statistics bugfixes.
- Support for application-specific Zabbix templates/checks.
- Alert endpoint for creating alerts with push.

Release 0.51.0
--------------
- Support for authentication token passing via query parameters.
- Alert API: historical and statistical.
- Support for historical quota usage/limit data via Zabbix backend.
- Filtering and minor API modifications across multiple endpoints.

Release 0.50.0
--------------
- New base structure for supporting of services.
- Support for NodeConductor extensions.
- Draft version of Oracle EM integration.
- Hook for invoice generation based on OpenStack Ceilometer data.
- Filtering and ordering API extensions.
- Draft of alerting API.

Release 0.49.1
--------------
- Bugfix of erred cloud recovery job.

Release 0.49.0
--------------
- Draft version of billing integration with WHMCS.
- Auto-recovery for CPMs if they pass health check.
- Demo API for the PaaS installation state monitoring.
- Bugfix: synchronize floating IP of OpenStack on membership synchronization.
- Exposure of several background tasks in admin.

Release 0.48.0
--------------
- Expose of requirements of mapped images in template list.
- UUID of objects is exposed in multiple endpoints.
- Bugfixes.

Release 0.47.0
--------------
- Added dummy JIRA client for faster development.
- Usability extensions of API: additional exposed fields and filterings.
- Support for user_data for OpenStack backend.
- Added dummy billing API.

Release 0.46.0
--------------
- Implemented foreground quotas for customers - support for limiting basic resources.
- Added dummy client for OpenStack backend. Allows to emulate actions of a backend for demo/development deployments.
- Added support for displaying, filtering and searching of events stored in ElasticSearch.
- Initial support of integration with JIRA for customer support.
  Bugfixes.

Release 0.45.0
--------------
- Migration to DRF 3.1 framework for REST, more consistent API.

Release 0.44.0
--------------
- Bugfixes.

Release 0.43.0
--------------
- Extended IaaS template filtering.
- Extended IaaS template with os_type and icon_name fields.
- Renamed 'hostname' field to 'name' in Instance and Resources.

Release 0.42.0
--------------
- Refactored OpenStack backups to use snapshots instead of full volume backups.
- Moved OpenStack credentials to DB from configuration. Old credential format is still supported.
- Added support for TZ in backup schedule definition.
- Introduced throttling for background tasks.

Release 0.41.0
--------------
- Introducing new quotas module prototype. Support for backend and frontend quotas.
- Introducing new template module prototype. Support for multi-service templates.
- Support for default availability zone of OpenStack deployment in configuration.
- Support for setting CPU overcommit ratio for OpenStack versions prior to Kilo.
- Change OpenStack tenant name generation schema. Now it uses only project UUID, name is removed.
- More resilient start/stop operations for OpenStack.
- Extended event log information for instance creation.
- Bugfixes.

Release 0.40.0
--------------
- Enhanced support of instance import - added ability to set template.
- Fix sorting of instances by start_time.

Release 0.39.0
--------------
- Added instance import helper.
- Improved event logging.
- Bugfixes of quota checks.

Release 0.38.0
--------------
- Optimized resource usage monitoring. Use background tasks for collecting statistics.
- Bugfix of listing service events.

Release 0.37.0
--------------
- More information added to existing event logs.
- Improved performance of querying resource statistics.
- Bugfixes of the event logger and service list.

Release 0.36.0
--------------
- UUIDs in emitted logs are not hyphenated.
- Bugfixes and documentation extensions.
- Default value for the maximal page_size was set to 200.

Release 0.35.0
--------------
- Added basic organization validation flow.
- Modified user filtering to take into account organization validation status.
- Bugfixes of the event logger.

Release 0.34.0
--------------
- Dropped backup quota. Rely on storage quota only.
- Added event logging for actions initiated by user or staff.

Release 0.33.0
--------------
- Improved user key propagation speed to the backend.
- Refactored OpenStack backups to use volumes only.

Release 0.32.0
--------------
- Staff users are now listed to staff users only.
- Bugfixes.

Release 0.31.0
--------------
- Bugfixes.

Release 0.30.0
--------------
- Bugfixes.

Release 0.29.0
--------------
- Bugfixes.

Release 0.28.0
--------------
- Scheduled backups are now run as Celery tasks.
- Changed quota usage to be re-calculated after each operation.
  It is regularly synced to assure that calculations are correct.

Release 0.27.0
--------------
- Added volume size parameters configuration to instance creation process.
- Added management command for creating staff user with a password from cli.
- Increased timeouts for provisioning operations.

Release 0.26.0
--------------
- Extended NodeConductor admin with new models/fields.
- Increased timeouts for volume and snapshot operations.
- Refactored key usage on provisioning - never fail fully.
- Multiple bugfixes.

Release 0.25.0
--------------
- Fixed usage statistic calculation to use average instead of summing.
- Refactored backup to accept user input.
- Refactored backup to use OpenStack volumes instead of volume backups. Drastic increase in speed.

Release 0.24.0
--------------
- Introduce vm instance restart action.
