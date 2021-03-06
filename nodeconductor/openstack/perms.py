from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic, StaffPermissionLogic
from nodeconductor.structure import models as structure_models, perms as structure_perms


PERMISSION_LOGICS = (
    ('openstack.OpenStackService', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': structure_models.CustomerRole.OWNER,
        },
        any_permission=True,
    )),
    ('openstack.OpenStackServiceProjectLink', FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            'service__customer__roles__permission_group__user',
            'project__project_groups__roles__permission_group__user',
        ],
        collaborators_filter=[
            {'service__customer__roles__role_type': structure_models.CustomerRole.OWNER},
            {'project__project_groups__roles__role_type': structure_models.ProjectGroupRole.MANAGER},
        ],
        any_permission=True,
    )),
    ('openstack.SecurityGroup', FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            'service_project_link__service__customer__roles__permission_group__user',
            'service_project_link__project__roles__permission_group__user',
            'service_project_link__project__project_groups__roles__permission_group__user',
        ],
        collaborators_filter=[
            {'service_project_link__service__customer__roles__role_type': structure_models.CustomerRole.OWNER},
            {'service_project_link__project__roles__role_type': structure_models.ProjectRole.ADMINISTRATOR},
            {'service_project_link__project__project_groups__roles__role_type':
             structure_models.ProjectGroupRole.MANAGER}
        ],
        any_permission=True,
    )),
    ('openstack.SecurityGroupRule', FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            'security_group__service_project_link__service__customer__roles__permission_group__user',
            'security_group__service_project_link__project__roles__permission_group__user',
            'security_group__service_project_link__project__project_groups__roles__permission_group__user',
        ],
        collaborators_filter=[
            {'security_group__service_project_link__service__customer__roles__role_type':
             structure_models.CustomerRole.OWNER},
            {'security_group__service_project_link__project__roles__role_type':
             structure_models.ProjectRole.ADMINISTRATOR},
            {'security_group__service_project_link__project__project_groups__roles__permission_group__user':
             structure_models.ProjectGroupRole.MANAGER},
        ],
        any_permission=True,
    )),
    ('openstack.Instance', structure_perms.resource_permission_logic),
    ('openstack.Flavor', StaffPermissionLogic(any_permission=True)),
    ('openstack.Image', StaffPermissionLogic(any_permission=True)),
    ('openstack.FloatingIP', StaffPermissionLogic(any_permission=True)),
)
