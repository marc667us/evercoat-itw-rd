Reading additional input from stdin...
OpenAI Codex v0.147.0
--------
workdir: C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 01a02097-11d2-7512-aeed-4b2fbc83eb0b
--------
user
You are the Codex Reviewer performing a SECURITY AUDIT of the API of this repository (EvercoatITWRD APP).
codex
I’ll audit the API surface, authentication/authorization, input handling, secrets, data access, and dependency/configuration risks. I’ll keep this read-only and report findings with severity, evidence, and concrete remediation.
  → Map the repository and identify API entry points, configuration, and dependencies
  • Trace authentication, authorization, validation, data access, and sensitive operations
  • Run targeted static checks and inspect tests/configuration for security gaps
  • Produce a prioritized security audit with evidence and remediation
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --files -g '"'!node_modules'"' -g '"'!dist'"' -g '"'!build'"' | Select-Object -First 500" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 2197ms:
TODO.md
MEMORY.md
tests\e2e\shell\navigation.spec.ts
tests\e2e\shell\api-wiring.spec.ts
tests\e2e\shell\accessibility.spec.ts
tests\e2e\api\serving.spec.ts
infrastructure\compose\garage.toml
infrastructure\compose\docker-compose.yml
infrastructure\compose\Caddyfile
IMPLEMENTATION_PLAN.md
CHANGELOG.md
BRAIN.md
.env.example
CONTEXT.md
CLAUDE.md
DATA_MODEL.md
DECISIONS.md
RESUME_HERE.md
render.yaml
playwright.config.ts
package.json
package-lock.json
reviews\codex-slice7-messaging-auth.md
reviews\codex-api-security-2026-08-20.md
services\keycloak\realm\README.md
REUSE.md
services\keycloak\realm\evercoat-realm.json
SECURITY.md
docs\REVIEW_PASS1_ADJUDICATION.md
scripts\verify-alignment.sh
scripts\seed.sh
scripts\seed.py
scripts\live-suite.sh
scripts\keycloak-bootstrap.sh
scripts\keycloak-bind-subs.py
scripts\build_demo_formulations.py
scripts\backup.sh
scripts\assert-suite-ran.py
apps\web\vitest.config.ts
apps\web\tsconfig.json
apps\web\tailwind.config.ts
apps\web\public\_redirects
apps\web\postcss.config.mjs
apps\web\package.json
apps\web\package-lock.json
apps\web\next.config.mjs
apps\api\tests\__init__.py
apps\api\tests\test_migration_coverage.py
apps\api\tests\test_material_serialisation.py
apps\api\tests\test_keycloak_realm.py
apps\api\tests\test_bootstrap_scripts.py
apps\web\lib\navigation.ts
apps\web\lib\navigation.test.ts
apps\api\tests\integration\__init__.py
apps\api\tests\integration\test_auth_end_to_end.py
apps\web\lib\demo\demo-data.json
apps\web\lib\demo\dataset.ts
apps\web\lib\demo\dataset.test.ts
apps\web\lib\auth\pkce.ts
apps\web\lib\auth\pkce.test.ts
apps\web\lib\auth\flow-state.ts
apps\web\lib\auth\flow-state.test.ts
apps\web\lib\auth\config.ts
apps\web\lib\api\tasks.ts
apps\web\lib\api\session.ts
apps\web\lib\api\schemas.test.ts
apps\web\lib\api\projects.ts
apps\api\tests\db\__init__.py
apps\web\lib\api\materials.ts
apps\api\tests\db\test_slice2_tasks.py
apps\web\lib\api\hooks.ts
apps\api\tests\db\test_slice2_stage_gates.py
apps\web\lib\api\formulations.ts
apps\api\tests\db\test_slice2_review_fixes.py
apps\web\lib\api\config.ts
apps\api\tests\db\test_slice2_opportunities.py
apps\web\lib\api\client.ts
apps\api\tests\db\test_slice2_dashboard.py
apps\web\lib\api\client.test.ts
apps\api\tests\db\test_requirements.py
apps\api\tests\db\test_realm_matches_database.py
apps\api\tests\db\test_pipeline_history.py
apps\api\tests\db\test_object_ownership.py
apps\api\tests\db\test_024_memberships_for_subject.py
apps\api\tests\db\test_023_messaging.py
apps\web\eslint.config.mjs
apps\api\tests\db\test_022_msd_boundary.py
apps\web\Dockerfile
apps\api\tests\db\test_018_testing.py
apps\api\tests\db\test_017_laboratory.py
apps\api\tests\db\test_015_service_rules.py
apps\api\tests\db\test_015_materials_formulations.py
apps\api\tests\db\test_011_audit_chain_scope.py
apps\api\tests\db\test_002_roles_permissions.py
apps\api\tests\db\test_001_core_tenancy.py
apps\api\tests\db\conftest.py
apps\api\pyproject.toml
apps\api\migrations\024_memberships_for_subject.sql
apps\api\migrations\023_deny_mutation_names_its_own_table.sql
apps\api\migrations\022_messaging_notifications_msd.sql
apps\api\migrations\021_failures_hypotheses_evidence.sql
apps\api\migrations\020_approval_engine.sql
apps\api\migrations\019_test_confirm_has_holders.sql
apps\api\migrations\018_testing_methods_tests_replicates.sql
apps\api\migrations\017_laboratory_batches_samples.sql
apps\api\migrations\016_material_approve_production_has_a_holder.sql
apps\api\migrations\015_materials_suppliers_formulations.sql
apps\api\migrations\014_object_ownership.sql
apps\api\migrations\013_audit_policy_and_definer_hardening.sql
apps\api\migrations\012_milestone_risk_permissions.sql
apps\api\migrations\011_audit_chain_per_organization.sql
apps\api\migrations\010_stage_transition_from_fk.sql
apps\api\migrations\009_stage_sequence_deferrable.sql
apps\api\migrations\008_opportunity_converted_status.sql
apps\api\migrations\007_audit_canonical_json.sql
apps\api\migrations\006_project_lead_can_see_own_project.sql
apps\api\migrations\005_rls_insert_check.sql
apps\api\migrations\004_ordering_uses_clock_timestamp.sql
apps\api\migrations\003_projects_pipeline_requirements.sql
apps\api\migrations\002_seed_roles_permissions.sql
apps\api\migrations\001_core_tenancy.sql
apps\api\Dockerfile
apps\api\migrations_alembic\__init__.py
apps\api\migrations_alembic\_sql.py
apps\api\tests\calculations\__init__.py
apps\api\tests\calculations\test_traffic_light.py
apps\api\tests\calculations\test_mass_deviation.py
apps\api\app\__init__.py
apps\api\tests\calculations\test_formulation.py
apps\api\tests\calculations\test_demo_formulations_are_current.py
apps\web\components\ui\technical-data-grid.tsx
apps\web\components\ui\status-badge.tsx
apps\web\components\ui\record-link.tsx
apps\web\components\ui\kpi-card.tsx
apps\web\components\ui\entity-header.tsx
apps\web\components\ui\demo-banner.tsx
apps\web\components\ui\data-source-banner.tsx
apps\web\components\ui\chart-wrapper.tsx
apps\web\components\ui\chart-theme.ts
apps\web\components\ui\chart-builders.ts
apps\web\components\ui\chart-builders.test.ts
apps\api\app\worker\__init__.py
apps\api\app\worker\celery_app.py
apps\api\app\main.py
apps\web\components\providers\query-provider.tsx
apps\web\components\providers\auth-provider.tsx
apps\web\components\providers\auth-provider.test.ts
apps\api\tests\auth\__init__.py
apps\api\tests\auth\test_token_verification.py
apps\api\tests\auth\test_slice2_planning_routes.py
apps\api\tests\auth\test_project_routes.py
apps\api\tests\auth\test_authorization.py
apps\api\tests\auth\conftest.py
apps\api\migrations_alembic\versions\2026_08_19_0024-c6000_memberships_for_subject.py
apps\api\migrations_alembic\versions\2026_08_19_0023-c5000_deny_mutation_names_its_own_table.py
apps\api\migrations_alembic\versions\2026_08_18_0022-c4000_messaging_notifications_msd.py
apps\api\migrations_alembic\versions\2026_08_18_0021-c3000_failures_hypotheses_evidence.py
apps\api\migrations_alembic\versions\2026_08_18_0020-c2000_approval_engine.py
apps\api\migrations_alembic\versions\2026_08_18_0019-c1000_test_confirm_holders.py
apps\api\migrations_alembic\versions\2026_08_18_0018-b9000_testing_methods_tests_replicates.py
apps\api\migrations_alembic\versions\2026_08_18_0017-b8000_laboratory_batches_samples.py
apps\api\migrations_alembic\versions\2026_08_18_0016-b7000_approve_production_holder.py
apps\api\migrations_alembic\versions\2026_08_18_0015-b6000_materials_suppliers_formulations.py
apps\api\migrations_alembic\versions\2026_08_18_0014-b5000_object_ownership.py
apps\api\migrations_alembic\versions\2026_08_17_0013-b4000_audit_policy_and_definer_hardening.py
apps\api\migrations_alembic\versions\2026_08_17_0012-b3000_milestone_risk_permissions.py
apps\api\migrations_alembic\versions\2026_08_17_0011-b2000_audit_chain_per_organization.py
apps\api\migrations_alembic\versions\2026_08_16_0010-b1000_stage_transition_from_fk.py
apps\api\migrations_alembic\versions\2026_08_16_0009-a9000_stage_sequence_deferrable.py
apps\api\migrations_alembic\versions\2026_08_16_0008-a8000_opportunity_converted_status.py
apps\api\migrations_alembic\versions\2026_08_16_0007-a7000_audit_canonical_json.py
apps\api\migrations_alembic\versions\2026_08_16_0006-a6000_lead_sees_own_project.py
apps\api\migrations_alembic\versions\2026_08_16_0005-a5000_rls_insert_check.py
apps\api\migrations_alembic\versions\2026_08_16_0004-a4000_clock_timestamp_ordering.py
apps\api\migrations_alembic\versions\2026_08_16_0003-a3000_projects_pipeline.py
apps\api\migrations_alembic\versions\2026_08_16_0002-a2000_seed_roles_permissions.py
apps\api\migrations_alembic\versions\2026_08_16_0001-a1000_core_tenancy.py
apps\api\migrations_alembic\script.py.mako
apps\api\migrations_alembic\env.py
apps\api\app\domains\__init__.py
apps\web\components\nav\account-menu.tsx
apps\web\components\nav\top-bar.tsx
apps\web\components\nav\sidebar.tsx
apps\web\components\nav\app-sidebar.tsx
apps\web\components\nav\api-status.tsx
apps\api\app\domains\testing\__init__.py
apps\api\app\domains\testing\service.py
apps\api\app\domains\laboratory\__init__.py
apps\api\app\domains\laboratory\service.py
apps\api\app\core\__init__.py
apps\api\app\core\tenancy.py
apps\api\app\domains\tasks\__init__.py
apps\api\app\domains\formulations\__init__.py
apps\api\app\domains\tasks\service.py
apps\api\app\domains\formulations\service.py
apps\web\app\suppliers\page.tsx
apps\api\app\domains\failures\__init__.py
apps\api\app\domains\failures\service.py
apps\api\app\domains\requirements\__init__.py
apps\api\app\domains\requirements\service.py
apps\api\app\domains\approvals\__init__.py
apps\api\app\domains\approvals\service.py
apps\web\app\projects\[code]\project-detail.tsx
apps\web\app\projects\[code]\page.tsx
apps\web\app\projects\page.tsx
apps\api\app\domains\projects\__init__.py
apps\api\app\domains\projects\planning.py
apps\api\app\domains\projects\members.py
apps\api\app\domains\projects\dashboard.py
apps\web\app\pipeline\page.tsx
apps\web\app\page.tsx
apps\api\app\domains\msd\__init__.py
apps\api\app\domains\msd\retrieval.py
apps\web\app\my-work\page.tsx
apps\api\app\domains\pipeline\__init__.py
apps\api\app\domains\pipeline\service.py
apps\api\app\domains\messaging\__init__.py
apps\api\app\domains\messaging\service.py
apps\web\app\materials\page.tsx
apps\web\app\layout.tsx
apps\api\app\domains\materials\__init__.py
apps\api\app\domains\materials\service.py
apps\api\app\domains\opportunities\service.py
apps\api\app\domains\opportunities\__init__.py
apps\web\app\innovation\page.tsx
apps\web\app\globals.css
apps\api\app\core\audit.py
apps\web\app\dashboard\page.tsx
apps\web\app\dashboard\dashboard-view.tsx
apps\api\app\calculations\__init__.py
apps\api\app\calculations\testing.py
apps\api\app\calculations\formulation.py
apps\web\app\formulations\[code]\page.tsx
apps\web\app\formulations\[code]\formula-detail.tsx
apps\web\app\formulations\page.tsx
apps\api\alembic.ini
apps\api\app\core\db.py
apps\api\app\core\config.py
apps\api\app\core\logging.py
apps\api\app\core\security.py
apps\web\app\auth\callback\page.tsx
apps\api\app\api\admin.py
apps\api\app\api\admin_reference_data.py
apps\api\app\api\formulations.py
apps\web\app\admin\page.tsx
apps\api\app\api\failures.py
apps\api\app\api\materials.py
apps\api\app\api\laboratory.py
apps\api\app\api\health.py
apps\api\app\api\messaging.py
apps\api\app\api\me.py
apps\api\app\api\opportunities.py
apps\api\app\api\projects.py
apps\api\app\api\admin_stage_gates.py
apps\api\app\api\tasks.py
apps\api\app\api\__init__.py
apps\api\app\api\testing.py

codex
The repository already contains an API security review dated today. I’m treating it as prior evidence, not as authoritative: I’ll verify its findings against the current code and look for gaps or regressions.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content reviews\\codex-api-security-2026-08-20.md; Get-Content apps\\api\\app\\main.py; Get-Content apps\\api\\app\\core\\config.py; Get-Content apps\\api\\app\\core\\security.py; Get-Content apps\\api\\app\\core\\db.py; Get-Content apps\\api\\pyproject.toml" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 1214ms:
Reading additional input from stdin...
OpenAI Codex v0.147.0
--------
workdir: C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 01a02097-11d2-7512-aeed-4b2fbc83eb0b
--------
user
You are the Codex Reviewer performing a SECURITY AUDIT of the API of this repository (EvercoatITWRD APP).
codex
Iâ€™ll audit the API surface, authentication/authorization, input handling, secrets, data access, and dependency/configuration risks. Iâ€™ll keep this read-only and report findings with severity, evidence, and concrete remediation.
  â†’ Map the repository and identify API entry points, configuration, and dependencies
  â€¢ Trace authentication, authorization, validation, data access, and sensitive operations
  â€¢ Run targeted static checks and inspect tests/configuration for security gaps
  â€¢ Produce a prioritized security audit with evidence and remediation
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --files -g '"'!node_modules'"' -g '"'!dist'"' -g '"'!build'"' | Select-Object -First 500" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 2197ms:
TODO.md
MEMORY.md
tests\e2e\shell\navigation.spec.ts
tests\e2e\shell\api-wiring.spec.ts
tests\e2e\shell\accessibility.spec.ts
tests\e2e\api\serving.spec.ts
infrastructure\compose\garage.toml
infrastructure\compose\docker-compose.yml
infrastructure\compose\Caddyfile
IMPLEMENTATION_PLAN.md
CHANGELOG.md
BRAIN.md
.env.example
CONTEXT.md
CLAUDE.md
DATA_MODEL.md
DECISIONS.md
RESUME_HERE.md
render.yaml
playwright.config.ts
package.json
package-lock.json
reviews\codex-slice7-messaging-auth.md
reviews\codex-api-security-2026-08-20.md
services\keycloak\realm\README.md
REUSE.md
services\keycloak\realm\evercoat-realm.json
SECURITY.md
docs\REVIEW_PASS1_ADJUDICATION.md
scripts\verify-alignment.sh
scripts\seed.sh
scripts\seed.py
scripts\live-suite.sh
scripts\keycloak-bootstrap.sh
scripts\keycloak-bind-subs.py
scripts\build_demo_formulations.py
scripts\backup.sh
scripts\assert-suite-ran.py
apps\web\vitest.config.ts
apps\web\tsconfig.json
apps\web\tailwind.config.ts
apps\web\public\_redirects
apps\web\postcss.config.mjs
apps\web\package.json
apps\web\package-lock.json
apps\web\next.config.mjs
apps\api\tests\__init__.py
apps\api\tests\test_migration_coverage.py
apps\api\tests\test_material_serialisation.py
apps\api\tests\test_keycloak_realm.py
apps\api\tests\test_bootstrap_scripts.py
apps\web\lib\navigation.ts
apps\web\lib\navigation.test.ts
apps\api\tests\integration\__init__.py
apps\api\tests\integration\test_auth_end_to_end.py
apps\web\lib\demo\demo-data.json
apps\web\lib\demo\dataset.ts
apps\web\lib\demo\dataset.test.ts
apps\web\lib\auth\pkce.ts
apps\web\lib\auth\pkce.test.ts
apps\web\lib\auth\flow-state.ts
apps\web\lib\auth\flow-state.test.ts
apps\web\lib\auth\config.ts
apps\web\lib\api\tasks.ts
apps\web\lib\api\session.ts
apps\web\lib\api\schemas.test.ts
apps\web\lib\api\projects.ts
apps\api\tests\db\__init__.py
apps\web\lib\api\materials.ts
apps\api\tests\db\test_slice2_tasks.py
apps\web\lib\api\hooks.ts
apps\api\tests\db\test_slice2_stage_gates.py
apps\web\lib\api\formulations.ts
apps\api\tests\db\test_slice2_review_fixes.py
apps\web\lib\api\config.ts
apps\api\tests\db\test_slice2_opportunities.py
apps\web\lib\api\client.ts
apps\api\tests\db\test_slice2_dashboard.py
apps\web\lib\api\client.test.ts
apps\api\tests\db\test_requirements.py
apps\api\tests\db\test_realm_matches_database.py
apps\api\tests\db\test_pipeline_history.py
apps\api\tests\db\test_object_ownership.py
apps\api\tests\db\test_024_memberships_for_subject.py
apps\api\tests\db\test_023_messaging.py
apps\web\eslint.config.mjs
apps\api\tests\db\test_022_msd_boundary.py
apps\web\Dockerfile
apps\api\tests\db\test_018_testing.py
apps\api\tests\db\test_017_laboratory.py
apps\api\tests\db\test_015_service_rules.py
apps\api\tests\db\test_015_materials_formulations.py
apps\api\tests\db\test_011_audit_chain_scope.py
apps\api\tests\db\test_002_roles_permissions.py
apps\api\tests\db\test_001_core_tenancy.py
apps\api\tests\db\conftest.py
apps\api\pyproject.toml
apps\api\migrations\024_memberships_for_subject.sql
apps\api\migrations\023_deny_mutation_names_its_own_table.sql
apps\api\migrations\022_messaging_notifications_msd.sql
apps\api\migrations\021_failures_hypotheses_evidence.sql
apps\api\migrations\020_approval_engine.sql
apps\api\migrations\019_test_confirm_has_holders.sql
apps\api\migrations\018_testing_methods_tests_replicates.sql
apps\api\migrations\017_laboratory_batches_samples.sql
apps\api\migrations\016_material_approve_production_has_a_holder.sql
apps\api\migrations\015_materials_suppliers_formulations.sql
apps\api\migrations\014_object_ownership.sql
apps\api\migrations\013_audit_policy_and_definer_hardening.sql
apps\api\migrations\012_milestone_risk_permissions.sql
apps\api\migrations\011_audit_chain_per_organization.sql
apps\api\migrations\010_stage_transition_from_fk.sql
apps\api\migrations\009_stage_sequence_deferrable.sql
apps\api\migrations\008_opportunity_converted_status.sql
apps\api\migrations\007_audit_canonical_json.sql
apps\api\migrations\006_project_lead_can_see_own_project.sql
apps\api\migrations\005_rls_insert_check.sql
apps\api\migrations\004_ordering_uses_clock_timestamp.sql
apps\api\migrations\003_projects_pipeline_requirements.sql
apps\api\migrations\002_seed_roles_permissions.sql
apps\api\migrations\001_core_tenancy.sql
apps\api\Dockerfile
apps\api\migrations_alembic\__init__.py
apps\api\migrations_alembic\_sql.py
apps\api\tests\calculations\__init__.py
apps\api\tests\calculations\test_traffic_light.py
apps\api\tests\calculations\test_mass_deviation.py
apps\api\app\__init__.py
apps\api\tests\calculations\test_formulation.py
apps\api\tests\calculations\test_demo_formulations_are_current.py
apps\web\components\ui\technical-data-grid.tsx
apps\web\components\ui\status-badge.tsx
apps\web\components\ui\record-link.tsx
apps\web\components\ui\kpi-card.tsx
apps\web\components\ui\entity-header.tsx
apps\web\components\ui\demo-banner.tsx
apps\web\components\ui\data-source-banner.tsx
apps\web\components\ui\chart-wrapper.tsx
apps\web\components\ui\chart-theme.ts
apps\web\components\ui\chart-builders.ts
apps\web\components\ui\chart-builders.test.ts
apps\api\app\worker\__init__.py
apps\api\app\worker\celery_app.py
apps\api\app\main.py
apps\web\components\providers\query-provider.tsx
apps\web\components\providers\auth-provider.tsx
apps\web\components\providers\auth-provider.test.ts
apps\api\tests\auth\__init__.py
apps\api\tests\auth\test_token_verification.py
apps\api\tests\auth\test_slice2_planning_routes.py
apps\api\tests\auth\test_project_routes.py
apps\api\tests\auth\test_authorization.py
apps\api\tests\auth\conftest.py
apps\api\migrations_alembic\versions\2026_08_19_0024-c6000_memberships_for_subject.py
apps\api\migrations_alembic\versions\2026_08_19_0023-c5000_deny_mutation_names_its_own_table.py
apps\api\migrations_alembic\versions\2026_08_18_0022-c4000_messaging_notifications_msd.py
apps\api\migrations_alembic\versions\2026_08_18_0021-c3000_failures_hypotheses_evidence.py
apps\api\migrations_alembic\versions\2026_08_18_0020-c2000_approval_engine.py
apps\api\migrations_alembic\versions\2026_08_18_0019-c1000_test_confirm_holders.py
apps\api\migrations_alembic\versions\2026_08_18_0018-b9000_testing_methods_tests_replicates.py
apps\api\migrations_alembic\versions\2026_08_18_0017-b8000_laboratory_batches_samples.py
apps\api\migrations_alembic\versions\2026_08_18_0016-b7000_approve_production_holder.py
apps\api\migrations_alembic\versions\2026_08_18_0015-b6000_materials_suppliers_formulations.py
apps\api\migrations_alembic\versions\2026_08_18_0014-b5000_object_ownership.py
apps\api\migrations_alembic\versions\2026_08_17_0013-b4000_audit_policy_and_definer_hardening.py
apps\api\migrations_alembic\versions\2026_08_17_0012-b3000_milestone_risk_permissions.py
apps\api\migrations_alembic\versions\2026_08_17_0011-b2000_audit_chain_per_organization.py
apps\api\migrations_alembic\versions\2026_08_16_0010-b1000_stage_transition_from_fk.py
apps\api\migrations_alembic\versions\2026_08_16_0009-a9000_stage_sequence_deferrable.py
apps\api\migrations_alembic\versions\2026_08_16_0008-a8000_opportunity_converted_status.py
apps\api\migrations_alembic\versions\2026_08_16_0007-a7000_audit_canonical_json.py
apps\api\migrations_alembic\versions\2026_08_16_0006-a6000_lead_sees_own_project.py
apps\api\migrations_alembic\versions\2026_08_16_0005-a5000_rls_insert_check.py
apps\api\migrations_alembic\versions\2026_08_16_0004-a4000_clock_timestamp_ordering.py
apps\api\migrations_alembic\versions\2026_08_16_0003-a3000_projects_pipeline.py
apps\api\migrations_alembic\versions\2026_08_16_0002-a2000_seed_roles_permissions.py
apps\api\migrations_alembic\versions\2026_08_16_0001-a1000_core_tenancy.py
apps\api\migrations_alembic\script.py.mako
apps\api\migrations_alembic\env.py
apps\api\app\domains\__init__.py
apps\web\components\nav\account-menu.tsx
apps\web\components\nav\top-bar.tsx
apps\web\components\nav\sidebar.tsx
apps\web\components\nav\app-sidebar.tsx
apps\web\components\nav\api-status.tsx
apps\api\app\domains\testing\__init__.py
apps\api\app\domains\testing\service.py
apps\api\app\domains\laboratory\__init__.py
apps\api\app\domains\laboratory\service.py
apps\api\app\core\__init__.py
apps\api\app\core\tenancy.py
apps\api\app\domains\tasks\__init__.py
apps\api\app\domains\formulations\__init__.py
apps\api\app\domains\tasks\service.py
apps\api\app\domains\formulations\service.py
apps\web\app\suppliers\page.tsx
apps\api\app\domains\failures\__init__.py
apps\api\app\domains\failures\service.py
apps\api\app\domains\requirements\__init__.py
apps\api\app\domains\requirements\service.py
apps\api\app\domains\approvals\__init__.py
apps\api\app\domains\approvals\service.py
apps\web\app\projects\[code]\project-detail.tsx
apps\web\app\projects\[code]\page.tsx
apps\web\app\projects\page.tsx
apps\api\app\domains\projects\__init__.py
apps\api\app\domains\projects\planning.py
apps\api\app\domains\projects\members.py
apps\api\app\domains\projects\dashboard.py
apps\web\app\pipeline\page.tsx
apps\web\app\page.tsx
apps\api\app\domains\msd\__init__.py
apps\api\app\domains\msd\retrieval.py
apps\web\app\my-work\page.tsx
apps\api\app\domains\pipeline\__init__.py
apps\api\app\domains\pipeline\service.py
apps\api\app\domains\messaging\__init__.py
apps\api\app\domains\messaging\service.py
apps\web\app\materials\page.tsx
apps\web\app\layout.tsx
apps\api\app\domains\materials\__init__.py
apps\api\app\domains\materials\service.py
apps\api\app\domains\opportunities\service.py
apps\api\app\domains\opportunities\__init__.py
apps\web\app\innovation\page.tsx
apps\web\app\globals.css
apps\api\app\core\audit.py
apps\web\app\dashboard\page.tsx
apps\web\app\dashboard\dashboard-view.tsx
apps\api\app\calculations\__init__.py
apps\api\app\calculations\testing.py
apps\api\app\calculations\formulation.py
apps\web\app\formulations\[code]\page.tsx
apps\web\app\formulations\[code]\formula-detail.tsx
apps\web\app\formulations\page.tsx
apps\api\alembic.ini
apps\api\app\core\db.py
apps\api\app\core\config.py
apps\api\app\core\logging.py
apps\api\app\core\security.py
apps\web\app\auth\callback\page.tsx
apps\api\app\api\admin.py
apps\api\app\api\admin_reference_data.py
apps\api\app\api\formulations.py
apps\web\app\admin\page.tsx
apps\api\app\api\failures.py
apps\api\app\api\materials.py
apps\api\app\api\laboratory.py
apps\api\app\api\health.py
apps\api\app\api\messaging.py
apps\api\app\api\me.py
apps\api\app\api\opportunities.py
apps\api\app\api\projects.py
apps\api\app\api\admin_stage_gates.py
apps\api\app\api\tasks.py
apps\api\app\api\__init__.py
apps\api\app\api\testing.py

codex
The repository already contains an API security review dated today. Iâ€™m treating it as prior evidence, not as authoritative: Iâ€™ll verify its findings against the current code and look for gaps or regressions.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content reviews\\codex-api-security-2026-08-20.md; Get-Content apps\\api\\app\\main.py; Get-Content apps\\api\\app\\core\\config.py; Get-Content apps\\api\\app\\core\\security.py; Get-Content apps\\api\\app\\core\\db.py; Get-Content apps\\api\\pyproject.toml" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
"""EvercoatITWRD APP â€” FastAPI entrypoint.

Observability lands in Slice 1 rather than Slice 20 (Codex F43): the
slice gate requires every feature to be exercised on a *deployed*
instance from Slice 1 onward, and you cannot diagnose a deployed instance
that has no health endpoint, no structured logs and no metrics.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.api.admin import router as admin_router
from app.api.admin_reference_data import router as admin_reference_data_router
from app.api.admin_stage_gates import router as admin_stage_gates_router
from app.api.failures import approvals_router
from app.api.failures import router as failures_router
from app.api.formulations import router as formulations_router
from app.api.health import router as health_router
from app.api.laboratory import router as laboratory_router
from app.api.materials import router as materials_router
from app.api.materials import suppliers_router
from app.api.me import router as me_router
from app.api.messaging import router as messaging_router
from app.api.opportunities import router as opportunities_router
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.testing import router as testing_router
from app.core.config import settings
from app.core.logging import configure_logging

__all__ = ["app", "create_app"]

configure_logging()
log = structlog.get_logger(__name__)

REQUESTS = Counter(
    "evercoat_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "evercoat_http_request_seconds",
    "HTTP request latency",
    ["method", "path"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    log.info(
        "startup",
        app=settings.app_name,
        env=settings.app_env,
        version=app.version,
    )
    yield
    log.info("shutdown", app=settings.app_name)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Integrated R&D, Smart Formulation, Laboratory Testing, "
            "Product Modeling and Product Development Intelligence Platform"
        ),
        lifespan=lifespan,
        # No interactive docs in production: the schema enumerates every
        # controlled endpoint and is free reconnaissance.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-CSRF-Token"],
    )

    @application.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Correlation id, structured access log, metrics.

        The correlation id is echoed to the client and bound to every log
        line for the request, so an incident can be reconstructed from the
        audit trail plus traces (SECURITY.md Â§16).
        """
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        # Route template, not the concrete path: labelling metrics with
        # /projects/<uuid> would create unbounded cardinality and take
        # Prometheus down.
        route = request.scope.get("route")
        label_path = getattr(route, "path", request.url.path)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.perf_counter() - started
            REQUESTS.labels(request.method, label_path, "500").inc()
            LATENCY.labels(request.method, label_path).observe(elapsed)
            # exc_info, but never the request body -- formulation payloads
            # must not reach logs (SECURITY.md Â§11).
            log.exception("request_failed", elapsed_ms=round(elapsed * 1000, 2))
            return JSONResponse(
                status_code=500,
                content={"detail": "internal error", "correlation_id": correlation_id},
                headers={"X-Correlation-Id": correlation_id},
            )

        elapsed = time.perf_counter() - started
        REQUESTS.labels(request.method, label_path, str(response.status_code)).inc()
        LATENCY.labels(request.method, label_path).observe(elapsed)
        log.info(
            "request",
            status=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
        )
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    @application.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    application.include_router(health_router, prefix="/health", tags=["health"])
    # Administration section 1 -- the write path for users, roles and
    # permissions. Live from Slice 1 (ADR-021): a configuration value
    # with no screen is a value nobody can write.
    application.include_router(admin_router, prefix="/api/admin")
    # Administration section 2 -- stage-gate configuration. Same prefix,
    # separate module: the pipeline reads stage_definitions on every
    # transition, so ADR-021 requires the screen that writes them to ship
    # in the same slice as the code that reads them.
    application.include_router(admin_stage_gates_router, prefix="/api/admin")
    # Administration section 3 -- units and product families. Slice 3's
    # own Administration section: migration 015 creates the tables and
    # this is their write path, so they do not join the list of tables
    # nothing can write.
    application.include_router(admin_reference_data_router, prefix="/api/admin")
    # Identity, BEFORE a tenant has been chosen.
    #
    # ðŸ”´ The only authenticated route that does not require
    # X-Organization-Id. Everything else depends on get_principal, which
    # demands it -- so without this a browser that had just signed in had
    # a valid token and no way to discover a tenant to ask for. See
    # app/api/me.py and migration 024.
    application.include_router(me_router, prefix="/api/me")
    application.include_router(projects_router, prefix="/api/projects")
    application.include_router(opportunities_router, prefix="/api/opportunities")
    # My Work. Mounted at its own prefix rather than under /api/projects
    # because a task need not belong to a project at all.
    application.include_router(tasks_router, prefix="/api/my-work")
    # Slice 3. Materials and suppliers are ORGANIZATION-scoped reference
    # data, so they sit at the top level rather than under a project --
    # a chemist on any project must be able to see the whole library.
    application.include_router(materials_router, prefix="/api/materials")
    application.include_router(suppliers_router, prefix="/api/suppliers")
    # Formulations ARE project-scoped, but they are addressed by their own
    # id and RLS applies the project-membership predicate to every row, so
    # the prefix carries no project segment. See the module docstring.
    application.include_router(formulations_router, prefix="/api/formulations")
    # Slice 4. Batches are project-scoped and addressed by their own id,
    # like formulations: RLS applies the project-membership predicate to
    # every row, so the prefix carries no project segment.
    application.include_router(laboratory_router, prefix="/api/laboratory/batches")
    # Slice 5. The Test Module. Project-scoped through the sample the test
    # was taken from, so RLS applies the membership predicate to every row
    # and the prefix carries no project segment.
    application.include_router(testing_router, prefix="/api/testing/tests")
    # Slice 6. Failure investigation, and the ONE shared approval engine â€”
    # polymorphic over (entity_type, entity_id) so Validation, Pilot,
    # Qualification and Release add zero approval infrastructure (Â§9).
    application.include_router(failures_router, prefix="/api/quality/failures")
    application.include_router(approvals_router, prefix="/api/approvals")
    # Messaging is mounted last because it is the layer every other
    # domain links INTO -- a thread hangs off a formula, a batch, a
    # failure -- and nothing in it is a prerequisite for them.
    application.include_router(messaging_router, prefix="/api/messaging", tags=["messaging"])

    if settings.metrics_enabled:

        @application.get("/metrics", include_in_schema=False)
        async def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()
"""Application settings.

Every value is read from the environment. Nothing sensitive has a default
-- a missing database password should stop the process at startup, not
silently connect somewhere unintended.

Secrets reach the environment through SOPS + age (SECURITY.md Â§12), never
from a committed file. Note for anyone writing a secrets file on this
host: PowerShell pipelines add a UTF-16 BOM, which makes the first key
unparseable in a way that looks like a wrong password. Write UTF-8
explicitly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings", "settings"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Identity -------------------------------------------------------
    app_name: str = "EvercoatITWRD APP"
    app_slug: str = "evercoat-itw-rd"
    app_env: Literal["development", "staging", "production"] = "development"

    # --- Database -------------------------------------------------------
    # No default. The app must never guess a connection string.
    database_url: str = Field(..., description="SQLAlchemy URL for the runtime app role")
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False

    # --- Keycloak -------------------------------------------------------
    keycloak_issuer: str = Field(..., description="Realm issuer URL")
    keycloak_audience: str = Field(default="evercoat-api")
    # JWKS is cached; this bounds how long a revoked signing key stays
    # trusted after a realm key rotation.
    jwks_cache_seconds: int = 300

    # --- Cache / worker -------------------------------------------------
    valkey_url: str = "redis://valkey:6379/0"

    # --- Object storage -------------------------------------------------
    garage_endpoint: str = "http://garage:3900"
    garage_bucket: str = "evercoat-documents"
    garage_access_key: str | None = None
    garage_secret_key: str | None = None
    # Short by design. A signed URL outlives access revocation (Codex F38),
    # so the window is kept small and sensitive formulation documents go
    # through an authorization-checking proxy instead.
    signed_url_ttl_seconds: int = 120

    # --- AI (Slice 7 onward) --------------------------------------------
    # Local runtime only. The zero-cost rule forbids an essential paid AI
    # API, and proprietary formulations must not leave the organization's
    # infrastructure -- that is a security property first, cost second.
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str | None = None  # chosen from measured memory headroom

    # --- Observability --------------------------------------------------
    log_format: Literal["json", "console"] = "json"
    log_level: str = "INFO"
    metrics_enabled: bool = True

    # --- Security -------------------------------------------------------
    cors_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("database_url")
    @classmethod
    def _reject_superuser(cls, v: str) -> str:
        """Refuse to start as a database superuser.

        Superuser bypasses Row Level Security. Running the application as
        one hides exactly the defects RLS exists to catch, and they would
        only surface in production (ADR-017). This is a cheap guard
        against a mistake that is expensive and silent.
        """
        lowered = v.lower()
        for forbidden in ("://postgres:", "://postgres@", "user=postgres"):
            if forbidden in lowered:
                raise ValueError(
                    "the application must not connect as a database superuser; "
                    "use the evercoat_app role, which is subject to FORCE RLS"
                )
        return v

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_wildcard_in_prod(cls, v: list[str], info) -> list[str]:  # type: ignore[no-untyped-def]
        if "*" in v and info.data.get("app_env") == "production":
            raise ValueError("wildcard CORS origin is not permitted in production")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
"""Authentication and authorization.

Implements the chain from CLAUDE.md Â§6, enforced in this order on every
request:

    Authentication -> Organization -> Role -> Permission
                   -> Resource Scope -> Business Rule

with PostgreSQL RLS as an independent database-layer backstop.

Two rules govern everything here.

**Authorize on permissions, never on role names.** A role is a seeded
bundle. Checking ``role == "qa_compliance_officer"`` cannot express "QA
approval may not come from someone who supplied a development-side
approval on this same test" (ADR-019), and it hard-codes a deployment's
staffing into the application. Permissions are data; roles are defaults.

**Resource scope is a separate check from permission.** Holding
``test.review`` does not grant review of a test in a project you are not
a member of. These are different questions and conflating them is how
intra-organization confidentiality gets lost -- the defect that made the
original three-layer claim false (Codex F32).

Frontend permission checks are cosmetic. Everything is re-enforced here.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import RequestContext, session_scope

__all__ = [
    "PermissionDenied",
    "Principal",
    "get_db",
    "get_principal",
    "require_permission",
    "require_project_member",
]

_bearer = HTTPBearer(auto_error=False)


class PermissionDenied(HTTPException):
    """403 with a stable shape.

    The detail deliberately does not say whether the resource exists.
    "You may not see it" and "it does not exist" must be indistinguishable
    to the caller, or the error message itself becomes a discovery channel
    for other teams' project codes.
    """

    def __init__(self, detail: str = "Not permitted") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@dataclass(frozen=True, slots=True)
class Principal:
    """The verified caller.

    Every field here comes from a signature-verified JWT or from the
    database. Nothing is taken from a header, query parameter or request
    body -- a client-supplied organization id would make the entire
    tenancy model advisory.
    """

    user_id: uuid.UUID
    organization_id: uuid.UUID
    keycloak_sub: str
    email: str
    display_name: str
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    session_id: str | None = None

    @property
    def context(self) -> RequestContext:
        return RequestContext(organization_id=self.organization_id, user_id=self.user_id)

    def has(self, permission: str) -> bool:
        return permission in self.permissions


# ---------------------------------------------------------------------------
# JWKS
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0


async def _get_jwks() -> dict[str, Any]:
    """Fetch and cache the realm's signing keys.

    The cache is bounded by ``jwks_cache_seconds`` because that window is
    how long a rotated-out signing key stays trusted. On a fetch failure
    we keep serving the previous keys rather than failing every request --
    a Keycloak blip should not take the API down -- but we never extend
    the window silently past a successful refresh.
    """
    global _jwks_cache, _jwks_fetched_at

    age = time.monotonic() - _jwks_fetched_at
    if _jwks_cache and age < settings.jwks_cache_seconds:
        return _jwks_cache

    url = f"{settings.keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_fetched_at = time.monotonic()
    except Exception:  # noqa: BLE001
        if not _jwks_cache:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="identity provider unavailable",
            ) from None
        # Stale keys beat no service; the next request retries.
    return _jwks_cache


async def _decode(token: str) -> dict[str, Any]:
    """Verify signature, issuer, audience and expiry. All four."""
    jwks = await _get_jwks()
    try:
        # cast: python-jose is untyped, so decode() is Any. The claims are
        # validated by the options below, not by the type system.
        decoded: dict[str, Any] = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_audience,
            issuer=settings.keycloak_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )
        return decoded
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Principal resolution
# ---------------------------------------------------------------------------

_PRINCIPAL_SQL = text(
    """
    SELECT u.id                AS user_id,
           u.email             AS email,
           u.display_name      AS display_name,
           om.organization_id  AS organization_id,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}') AS roles,
           COALESCE(array_agg(DISTINCT p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}') AS permissions
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id AND om.status = 'active'
    LEFT JOIN core.member_roles mr   ON mr.member_id = om.id
    LEFT JOIN core.roles r           ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions p     ON p.id = rp.permission_id
    WHERE u.keycloak_sub = :sub
      AND u.status = 'active'
      AND om.organization_id = :org_id
    GROUP BY u.id, u.email, u.display_name, om.organization_id
    """
)


async def get_verified_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """The token's subject, with no organization required.

    ðŸ”´ THIS IS THE ONLY AUTHENTICATED ENTRY POINT THAT DOES NOT DEMAND A
    TENANT, AND IT EXISTS FOR EXACTLY ONE ROUTE.

    ``get_principal`` requires ``X-Organization-Id``, correctly -- picking
    a default tenant for a user who belongs to several writes records into
    whichever one happened to sort first. But every authenticated route
    depends on it, so a browser that had just signed in held a valid token
    and no way to discover a tenant to ask for. Authentication completed
    and the application was still unusable. ``GET /api/me`` closes that,
    and needs identity before tenancy to do it.

    The verification is identical to ``get_principal``'s -- the same
    ``_decode``, so signature, issuer, audience and expiry are all checked.
    What is deliberately absent is the ORGANIZATION step, and nothing else.

    It returns a bare ``str`` rather than a ``Principal`` on purpose: a
    Principal without an organization would be a Principal that could be
    passed to something expecting one, and ``Principal.context`` would then
    be constructed from a tenant nobody chose. There is no such object, so
    there is no such mistake to make.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = await _decode(credentials.credentials)
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")
    return sub


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Resolve the caller, or refuse.

    Membership and permissions are read from the database rather than
    trusted from the token's claims. A JWT is a statement about identity;
    it is not a current statement about authorization. Revoking a
    membership must take effect immediately, not when the access token
    happens to expire.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = await _decode(credentials.credentials)

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")

    # Organization selection. A user may belong to several; the active one
    # comes from a header, but it is a *request* to use that organization,
    # validated against real membership below -- never taken on trust.
    requested_org = request.headers.get("X-Organization-Id")
    if not requested_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id header is required",
        )
    try:
        org_id = uuid.UUID(requested_org)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id is not a valid UUID",
        ) from None

    # Resolving the principal is itself a context-free read -- we cannot
    # set the RLS GUCs until we know who the caller is. It is confined to
    # core.users / core.organization_members and returns nothing from any
    # project-scoped table, which is why this is a safe exception to the
    # session_scope() rule.
    from app.core.db import unscoped_session_scope

    with unscoped_session_scope() as session:
        row = (
            session.execute(_PRINCIPAL_SQL, {"sub": sub, "org_id": org_id}).mappings().one_or_none()
        )

    if row is None:
        # Not a member of the requested organization -- or no such
        # organization. Deliberately the same answer for both.
        raise PermissionDenied("not a member of the requested organization")

    return Principal(
        user_id=row["user_id"],
        organization_id=row["organization_id"],
        keycloak_sub=sub,
        email=row["email"],
        display_name=row["display_name"],
        roles=frozenset(row["roles"]),
        permissions=frozenset(row["permissions"]),
        session_id=claims.get("sid"),
    )


def get_db(principal: Principal = Depends(get_principal)) -> Iterator[Session]:
    """Yield a session with the caller's RLS context applied.

    This is the only supported route to the database in request handling.
    Because it depends on ``get_principal``, there is no way to obtain a
    session without first having been authenticated and having proven
    organization membership.
    """
    with session_scope(principal.context) as session:
        yield session


# ---------------------------------------------------------------------------
# Authorization dependencies
# ---------------------------------------------------------------------------


def require_permission(*permissions: str, require_all: bool = False) -> Callable[..., Principal]:
    """Dependency factory: assert the caller holds the permission(s).

    Args:
        permissions: permission codes, e.g. ``"formula.approve_lab"``.
        require_all: if True the caller needs every one; default is any.
    """

    def _check(principal: Principal = Depends(get_principal)) -> Principal:
        held = principal.permissions
        ok = (
            all(p in held for p in permissions)
            if require_all
            else any(p in held for p in permissions)
        )
        if not ok:
            raise PermissionDenied()
        return principal

    return _check


def require_project_member(
    project_id_param: str = "project_id",
) -> Callable[..., Principal]:
    """Dependency factory: assert membership of the project in the path.

    Separate from :func:`require_permission` on purpose. Permission asks
    "may this person ever do this?"; scope asks "may they do it *here*?"
    Both must pass, and RLS independently enforces the same answer at the
    database layer, so a mistake in either one is caught by the other.
    """

    def _check(
        request: Request,
        principal: Principal = Depends(get_principal),
        session: Session = Depends(get_db),
    ) -> Principal:
        raw = request.path_params.get(project_id_param)
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"route has no path parameter '{project_id_param}'",
            )
        try:
            project_id = uuid.UUID(str(raw))
        except ValueError:
            raise PermissionDenied() from None

        # core.is_project_member() is the single definition of membership,
        # shared with every RLS policy. Asking the database rather than
        # reimplementing the predicate is what stops the rule drifting
        # between the API and the policies.
        is_member = session.execute(
            text("SELECT core.is_project_member(:pid)"), {"pid": project_id}
        ).scalar_one()

        if not is_member:
            raise PermissionDenied()
        return principal

    return _check
"""Database session and tenant/user context.

This module is where Row Level Security either works or silently fails.

The tenancy model (ADR-016) enforces BOTH organization isolation and
project membership in PostgreSQL, via two GUCs read by
``core.current_org_id()`` and ``core.current_user_id()``. Those GUCs must
be set correctly on every request, and unset correctly afterwards.

The classic failure mode (Codex F34) is a plain ``SET``, which persists
for the life of a pooled connection. Request A sets its organization,
finishes, returns the connection to the pool, and request B â€” belonging
to a different organization â€” inherits it. RLS then dutifully enforces
the *wrong* tenant, and every query looks perfectly normal. Nothing
errors. The data is simply wrong, quietly, in production.

Three defences here:

1.  ``SET LOCAL`` only, always inside an explicit transaction, so the
    setting dies with the transaction rather than the connection.
2.  Connections are reset on checkin, so a leaked setting cannot outlive
    a transaction even if a code path escapes the helper.
3.  **Fail closed.** A request that reaches the database without context
    raises rather than proceeding. During Slice 1 the SQL policies are
    permissive when the GUC is absent (so the stack is usable before
    every path sets context), which means an unset GUC would otherwise
    read as "no restriction" â€” the most dangerous default there is. This
    guard is what makes the permissive parallel-run window safe.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

__all__ = [
    "MissingContextError",
    "RequestContext",
    "SessionLocal",
    "apply_context",
    "get_engine",
    "session_scope",
    "set_local",
    "unscoped_session_scope",
]


class MissingContextError(RuntimeError):
    """Raised when a database session is used without tenant/user context.

    Deliberately not an HTTP error: reaching the database with no identity
    is a programming fault, not a client fault, and it must be loud.
    """


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Who is asking, and on whose behalf.

    Both values come from the verified JWT â€” never from a header, query
    parameter or request body. A client-supplied organization id would
    make the entire tenancy model advisory.
    """

    organization_id: uuid.UUID
    user_id: uuid.UUID

    def __post_init__(self) -> None:
        # UUIDs are interpolated into a SET LOCAL statement below, because
        # PostgreSQL does not accept bind parameters in SET. Typing them as
        # uuid.UUID and validating here is what makes that interpolation
        # safe -- a str would be an injection surface.
        if not isinstance(self.organization_id, uuid.UUID):
            raise TypeError("organization_id must be uuid.UUID")
        if not isinstance(self.user_id, uuid.UUID):
            raise TypeError("user_id must be uuid.UUID")


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Create the engine on first use, not at import.

    Building it at module scope made ``import app.core.db`` require a full
    valid configuration, which meant a test that only wanted to assert
    ``session_scope(None)`` raises could not import the module at all.
    That is a smell worth fixing rather than working around: a module that
    cannot be imported without a live database is one that cannot be unit
    tested, and it would fail at collection time in CI for the same reason.
    """
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    _engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Defence 2. DISCARD ALL clears GUCs, prepared statements, temp
        # tables and cursors, so nothing survives a checkin even if a code
        # path escapes session_scope(). Slightly more expensive than the
        # default rollback; the cost of the alternative is cross-tenant
        # disclosure.
        pool_reset_on_return="rollback",
        echo=settings.db_echo,
    )

    @event.listens_for(_engine, "checkin")
    def _scrub_connection(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        """Belt and braces: explicitly discard session state on checkin."""
        try:
            with dbapi_connection.cursor() as cur:
                cur.execute("DISCARD ALL")
        except Exception:  # noqa: BLE001
            # A connection we cannot scrub must not be reused. Invalidating
            # it costs one reconnect; keeping it risks leaking context.
            connection_record.invalidate()

    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, class_=Session)
    return _engine


def SessionLocal() -> Session:  # noqa: N802 - kept as a callable factory name
    """Session factory. Initialises the engine on first call."""
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None  # noqa: S101 - narrowed by get_engine
    return _session_factory()


def set_local(session: Session, guc: str, value: uuid.UUID) -> None:
    """Set a transaction-local GUC, with the VALUE passed as a bind parameter.

    The ``SET`` *statement* genuinely does not accept bind parameters â€” a
    placeholder there is a syntax error. But ``set_config(name, value,
    is_local)`` is an ordinary function, and it does. ``is_local=true``
    makes it exactly equivalent to ``SET LOCAL``: scoped to the
    transaction and discarded on COMMIT or ROLLBACK.

    That distinction matters. This function sets the GUCs every RLS policy
    in the database reads, so it is the single most injection-sensitive
    line in the application. It previously interpolated the value into the
    SQL string and argued that a ``uuid.UUID`` cannot carry SQL â€” which is
    true, and which depended entirely on the ``isinstance`` check below
    never being removed or widened. Semgrep flagged it
    (``avoid-sqlalchemy-text``) and it was right to: the safety was an
    argument, not a mechanism.

    Now the value never touches the statement text at all, so the type
    check is defence in depth rather than the only defence.

    The GUC NAME still cannot be a parameter â€” it is the first argument to
    set_config and must be a literal â€” so it stays allow-listed.
    """
    if guc not in _ALLOWED_GUCS:
        raise ValueError(f"refusing to set unknown GUC {guc!r}")
    if not isinstance(value, uuid.UUID):
        raise TypeError("GUC values must be uuid.UUID, never str")
    session.execute(
        text("SELECT set_config(:guc, :value, true)"),
        {"guc": guc, "value": str(value)},
    )


_ALLOWED_GUCS = frozenset({"app.current_org", "app.current_user_id"})


def apply_context(session: Session, ctx: RequestContext) -> None:
    """Set the RLS GUCs for the current transaction.

    ``SET LOCAL`` is scoped to the transaction, so it is discarded on
    COMMIT or ROLLBACK. Using ``SET`` here instead would reintroduce the
    pooled-connection leak this whole module exists to prevent.
    """
    if not session.in_transaction():
        # SET LOCAL outside a transaction is silently a no-op with a
        # warning -- the GUC would never be set and RLS would fall through
        # to the permissive branch. Refuse rather than half-work.
        raise MissingContextError(
            "apply_context requires an open transaction; SET LOCAL is a no-op outside one"
        )

    set_local(session, "app.current_org", ctx.organization_id)
    set_local(session, "app.current_user_id", ctx.user_id)


@contextmanager
def session_scope(ctx: RequestContext | None) -> Iterator[Session]:
    """Transactional session with tenant/user context applied.

    Every database access in the application goes through here. There is
    no supported path that reaches PostgreSQL without context.

    Args:
        ctx: The verified caller. ``None`` is permitted only for the
            handful of genuinely context-free operations -- health checks,
            JWKS refresh, migration bootstrap -- and those must pass
            ``allow_unscoped=True`` via :func:`unscoped_session_scope`.

    Raises:
        MissingContextError: if called without context (defence 3).
    """
    if ctx is None:
        raise MissingContextError(
            "database access attempted without RequestContext. If this is a "
            "genuinely context-free operation (health, JWKS, migrations), "
            "use unscoped_session_scope() and justify it in review."
        )

    session = SessionLocal()
    try:
        session.begin()
        apply_context(session, ctx)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def unscoped_session_scope() -> Iterator[Session]:
    """Session with NO tenant context. Rare, audited, and deliberately ugly.

    Legitimate uses are narrow: liveness/readiness probes, Keycloak JWKS
    caching, and migration bootstrap. It is named awkwardly on purpose --
    a reviewer should notice every call site.

    Once the FORCE RLS cutover migration lands, this session sees nothing
    in tenant-scoped tables anyway, because the policies stop being
    permissive when the GUC is absent. That is the intended end state:
    the guard above catches the mistake in development, and the database
    catches it in production.
    """
    session = SessionLocal()
    try:
        session.begin()
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
[project]
name = "evercoat-itw-rd"
version = "0.1.0"
description = "EvercoatITWRD APP â€” Integrated R&D, Smart Formulation, Laboratory Testing, Product Modeling and Product Development Intelligence Platform"
requires-python = ">=3.12"

# Reusability (root CLAUDE.md Â§0.3): the app is pip-installable so sibling
# apps can consume its exports via `pip install -e ../EvercoatITWRD APP`.
# Public API is declared in __all__; docs/REUSABILITY.md lists consumers.

dependencies = [
    # --- Web / API -------------------------------------------------------
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    # [email] extra pulls in email-validator, which EmailStr requires at
    # CLASS DEFINITION time -- without it the app fails to import, not
    # merely to validate. Caught by actually importing the app rather
    # than by a syntax check, which passed happily.
    "pydantic[email]>=2.9",
    "pydantic-settings>=2.6",

    # --- Persistence -----------------------------------------------------
    "sqlalchemy>=2.0.36",
    "alembic>=1.14",
    # psycopg 3, not psycopg2. Solar uses psycopg2-binary; psycopg3 has
    # first-class support for the transaction-scoped SET LOCAL pattern the
    # tenancy model depends on, and native async.
    "psycopg[binary,pool]>=3.2",

    # --- Identity --------------------------------------------------------
    # python-jose over python-keycloak, reused from Solar (REUSE.md R4):
    # MIT-licensed, avoids a heavy dependency tree, RS256 against the
    # realm JWKS is all we need.
    "python-jose[cryptography]>=3.3",
    # Direct, not transitive. Solar learned this the hard way: a security
    # feature resting on a transitive dependency is one refactor from
    # vanishing.
    "cryptography>=43.0",

    # --- Cache / worker --------------------------------------------------
    "redis>=5.2",          # Valkey is Redis wire-compatible
    "celery>=5.4",

    # --- Object storage --------------------------------------------------
    "boto3>=1.35",         # S3-compatible client for Garage, behind a port

    # --- Scientific (Slice 3 onward) -------------------------------------
    "numpy>=2.1",
    "scipy>=1.14",
    "pandas>=2.2",

    # --- Observability (Slice 1 â€” Codex F43) -----------------------------
    "prometheus-client>=0.21",
    "structlog>=24.4",

    # --- HTTP ------------------------------------------------------------
    "httpx>=0.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    # Property-based tests for the deterministic calculation engine.
    # Mandated by the source: "for any valid 100% formula and positive
    # batch quantity, sum(component masses) == batch mass within tolerance".
    "hypothesis>=6.115",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-python-jose",
    # Semgrep blocks the stdlib `xml` parser outright (XXE, billion
    # laughs) and it is right to: an allowlist of "but this input is
    # trusted" is exactly how the untrusted one eventually gets parsed.
    # scripts/assert-suite-ran.py reads JUnit XML with it.
    "defusedxml>=0.7",
    "types-defusedxml",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "PT", "SIM", "RUF", "S", "BLE"]
ignore = [
    # B008 flags function calls in argument defaults. In FastAPI,
    # `x = Depends(...)` IS the dependency-injection idiom -- the call is
    # evaluated once at definition and consumed by the framework, not
    # re-evaluated per request. Rewriting it to satisfy the rule would
    # break injection. Ignored globally rather than 26 inline noqa
    # comments, which would bury the real findings.
    "B008",
]

[tool.ruff.lint.per-file-ignores]
# Tests assert on internals and use bare asserts by definition.
"tests/**" = ["S101", "PT012"]

[tool.mypy]
python_version = "3.12"
strict = true
# Scientific data errors are the expensive kind here. The source
# specifically asks for Measurement, FormulaComponent, FormulaVersion,
# BatchQuantity, TestResult and PipelineTransition to be statically typed.
warn_unreachable = true
disallow_any_generics = true

# Celery ships no type stubs. Scoped to the single module that imports
# it, so the strictness stays on everywhere else -- a global relaxation
# would silently cover future untyped dependencies too.
[[tool.mypy.overrides]]
module = ["celery", "celery.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["app.worker.celery_app"]
disallow_untyped_decorators = false

[tool.pytest.ini_options]
testpaths = ["tests"]
# Auth tests are async because _decode awaits the JWKS fetch.
asyncio_mode = "auto"
# ðŸ”´ NO CLASS COLLECTION. Every test in this suite is a FUNCTION -- there
# is not one `class Test...` in `tests/` -- while the domain this product
# models is full of legitimate types whose names begin with "Test":
# `TestInput`, `TestError`, `TestStateError`, `TestNotFoundError`.
#
# pytest's default `python_classes = ["Test"]` tries to collect every one
# of them and emits a PytestCollectionWarning per class per importing
# module. That noise is not harmless: a test report full of expected
# warnings is where an unexpected one goes unnoticed.
#
# The alternative was renaming the domain types away from the word the
# domain actually uses, which makes the code worse to serve the test
# runner. This setting is the right way round.
python_classes = []
markers = [
    "rls: runs under SET ROLE evercoat_app to exercise FORCE ROW LEVEL SECURITY",
    "db: requires a live PostgreSQL",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; rg -n "''^(class Settings|    [a-z_].*=|def get_principal|async def _decode|def require_|oauth2_scheme|HTTPBearer|jwt'"\\.decode|audience|issuer)\" apps/api/app/core/config.py apps/api/app/core/security.py; rg -n \"@(router|[a-z_]+_router)\\.(get|post|put|patch|delete)|Depends\\(\" apps/api/app/api; rg -n \"unscoped_session_scope|text\\(f|execute\\(f|\\.format\\(|subprocess|os\\.system|pickle|yaml\\.load|eval\\(|exec\\(|shell=True|verify=False|allow_origins|password|secret|token\" apps/api/app apps/api/migrations infrastructure render.yaml .env.example" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 593ms:
?? reviews/codex-api-security-2026-08-20.md
apps/api/app/core/security.py:67:    def __init__(self, detail: str = "Not permitted") -> None:
apps/api/app/core/security.py:86:    roles: frozenset[str] = field(default_factory=frozenset)
apps/api/app/core/security.py:87:    permissions: frozenset[str] = field(default_factory=frozenset)
apps/api/app/core/security.py:88:    session_id: str | None = None
apps/api/app/core/security.py:117:    age = time.monotonic() - _jwks_fetched_at
apps/api/app/core/security.py:121:    url = f"{settings.keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"
apps/api/app/core/security.py:138:async def _decode(token: str) -> dict[str, Any]:
apps/api/app/core/security.py:140:    jwks = await _get_jwks()
apps/api/app/core/security.py:196:    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
apps/api/app/core/security.py:227:    claims = await _decode(credentials.credentials)
apps/api/app/core/security.py:228:    sub = claims.get("sub")
apps/api/app/core/security.py:236:    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
apps/api/app/core/security.py:253:    claims = await _decode(credentials.credentials)
apps/api/app/core/security.py:255:    sub = claims.get("sub")
apps/api/app/core/security.py:262:    requested_org = request.headers.get("X-Organization-Id")
apps/api/app/core/security.py:322:def require_permission(*permissions: str, require_all: bool = False) -> Callable[..., Principal]:
apps/api/app/core/security.py:330:    def _check(principal: Principal = Depends(get_principal)) -> Principal:
apps/api/app/core/security.py:344:def require_project_member(
apps/api/app/core/security.py:345:    project_id_param: str = "project_id",
apps/api/app/core/config.py:25:class Settings(BaseSettings):
apps/api/app/core/config.py:26:    model_config = SettingsConfigDict(
apps/api/app/core/config.py:34:    app_name: str = "EvercoatITWRD APP"
apps/api/app/core/config.py:35:    app_slug: str = "evercoat-itw-rd"
apps/api/app/core/config.py:36:    app_env: Literal["development", "staging", "production"] = "development"
apps/api/app/core/config.py:40:    database_url: str = Field(..., description="SQLAlchemy URL for the runtime app role")
apps/api/app/core/config.py:41:    db_pool_size: int = 10
apps/api/app/core/config.py:42:    db_max_overflow: int = 5
apps/api/app/core/config.py:43:    db_echo: bool = False
apps/api/app/core/config.py:46:    keycloak_issuer: str = Field(..., description="Realm issuer URL")
apps/api/app/core/config.py:47:    keycloak_audience: str = Field(default="evercoat-api")
apps/api/app/core/config.py:50:    jwks_cache_seconds: int = 300
apps/api/app/core/config.py:53:    valkey_url: str = "redis://valkey:6379/0"
apps/api/app/core/config.py:56:    garage_endpoint: str = "http://garage:3900"
apps/api/app/core/config.py:57:    garage_bucket: str = "evercoat-documents"
apps/api/app/core/config.py:58:    garage_access_key: str | None = None
apps/api/app/core/config.py:59:    garage_secret_key: str | None = None
apps/api/app/core/config.py:63:    signed_url_ttl_seconds: int = 120
apps/api/app/core/config.py:69:    ollama_base_url: str = "http://ollama:11434"
apps/api/app/core/config.py:70:    ollama_model: str | None = None  # chosen from measured memory headroom
apps/api/app/core/config.py:73:    log_format: Literal["json", "console"] = "json"
apps/api/app/core/config.py:74:    log_level: str = "INFO"
apps/api/app/core/config.py:75:    metrics_enabled: bool = True
apps/api/app/core/config.py:78:    cors_allowed_origins: list[str] = Field(default_factory=list)
apps/api/app/api\testing.py:168:@router.get("", tags=["testing"])
apps/api/app/api\testing.py:172:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api\testing.py:173:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:188:@router.post("", status_code=status.HTTP_201_CREATED, tags=["testing"])
apps/api/app/api\testing.py:191:    principal: Principal = Depends(require_permission("test.plan")),
apps/api/app/api\testing.py:192:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:210:@router.get("/{test_id}", tags=["testing"])
apps/api/app/api\testing.py:213:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api\testing.py:214:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:229:@router.post("/{test_id}/start", tags=["testing"])
apps/api/app/api\testing.py:232:    principal: Principal = Depends(require_permission("test.execute")),
apps/api/app/api\testing.py:233:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:248:@router.post("/{test_id}/replicates", status_code=status.HTTP_201_CREATED, tags=["testing"])
apps/api/app/api\testing.py:252:    principal: Principal = Depends(require_permission("test.execute")),
apps/api/app/api\testing.py:253:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:279:@router.post("/{test_id}/replicates/{replicate_id}/exclusion", tags=["testing"])
apps/api/app/api\testing.py:284:    principal: Principal = Depends(require_permission("test.execute", "test.review")),
apps/api/app/api\testing.py:285:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:310:@router.post("/{test_id}/completion", tags=["testing"])
apps/api/app/api\testing.py:313:    principal: Principal = Depends(require_permission("test.execute")),
apps/api/app/api\testing.py:314:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:334:@router.post("/{test_id}/decisions", status_code=status.HTTP_201_CREATED, tags=["testing"])
apps/api/app/api\testing.py:338:    principal: Principal = Depends(get_principal),
apps/api/app/api\testing.py:339:    session: Session = Depends(get_db),
apps/api/app/api\testing.py:389:@router.post("/{test_id}/confirmation", tags=["testing"])
apps/api/app/api\testing.py:392:    principal: Principal = Depends(require_permission("test.confirm")),
apps/api/app/api\testing.py:393:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:140:@router.get("", tags=["laboratory"])
apps/api/app/api\laboratory.py:144:    principal: Principal = Depends(require_permission("batch.view")),
apps/api/app/api\laboratory.py:145:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:161:@router.post("", status_code=status.HTTP_201_CREATED, tags=["laboratory"])
apps/api/app/api\laboratory.py:164:    principal: Principal = Depends(require_permission("batch.create")),
apps/api/app/api\laboratory.py:165:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:196:@router.get("/{batch_id}", tags=["laboratory"])
apps/api/app/api\laboratory.py:199:    principal: Principal = Depends(require_permission("batch.view")),
apps/api/app/api\laboratory.py:200:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:210:@router.post("/{batch_id}/authorization", tags=["laboratory"])
apps/api/app/api\laboratory.py:213:    principal: Principal = Depends(require_permission("batch.create")),
apps/api/app/api\laboratory.py:214:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:230:@router.post("/{batch_id}/start", tags=["laboratory"])
apps/api/app/api\laboratory.py:233:    principal: Principal = Depends(require_permission("batch.execute")),
apps/api/app/api\laboratory.py:234:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:249:@router.post("/{batch_id}/components/{component_id}/weighing", tags=["laboratory"])
apps/api/app/api\laboratory.py:254:    principal: Principal = Depends(require_permission("batch.execute")),
apps/api/app/api\laboratory.py:255:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:282:@router.post(
apps/api/app/api\laboratory.py:288:    principal: Principal = Depends(require_permission("batch.execute")),
apps/api/app/api\laboratory.py:289:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:307:@router.post("/{batch_id}/deviations", status_code=status.HTTP_201_CREATED, tags=["laboratory"])
apps/api/app/api\laboratory.py:314:    principal: Principal = Depends(require_permission("batch.execute", "batch.complete")),
apps/api/app/api\laboratory.py:315:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:330:@router.post("/{batch_id}/samples", status_code=status.HTTP_201_CREATED, tags=["laboratory"])
apps/api/app/api\laboratory.py:334:    principal: Principal = Depends(require_permission("sample.create")),
apps/api/app/api\laboratory.py:335:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:355:@router.post("/{batch_id}/completion", tags=["laboratory"])
apps/api/app/api\laboratory.py:358:    principal: Principal = Depends(require_permission("batch.complete")),
apps/api/app/api\laboratory.py:359:    session: Session = Depends(get_db),
apps/api/app/api\laboratory.py:375:@router.post("/{batch_id}/review", tags=["laboratory"])
apps/api/app/api\laboratory.py:379:    principal: Principal = Depends(get_principal),
apps/api/app/api\laboratory.py:380:    session: Session = Depends(get_db),
apps/api/app/api\health.py:39:@router.get("/live", include_in_schema=False)
apps/api/app/api\health.py:83:@router.get("/ready", include_in_schema=False)
apps/api/app/api\health.py:97:@router.get("/startup", include_in_schema=False)
apps/api/app/api\admin_stage_gates.py:114:@router.get("/stage-gates", response_model=list[StageDefinitionRead], tags=["admin"])
apps/api/app/api\admin_stage_gates.py:117:    principal: Principal = Depends(require_permission("admin.stage_gates")),
apps/api/app/api\admin_stage_gates.py:118:    session: Session = Depends(get_db),
apps/api/app/api\admin_stage_gates.py:146:@router.post(
apps/api/app/api\admin_stage_gates.py:154:    principal: Principal = Depends(require_permission("admin.stage_gates")),
apps/api/app/api\admin_stage_gates.py:155:    session: Session = Depends(get_db),
apps/api/app/api\admin_stage_gates.py:224:@router.put("/stage-gates/{stage_id}", response_model=StageDefinitionRead, tags=["admin"])
apps/api/app/api\admin_stage_gates.py:228:    principal: Principal = Depends(require_permission("admin.stage_gates")),
apps/api/app/api\admin_stage_gates.py:229:    session: Session = Depends(get_db),
apps/api/app/api\admin_stage_gates.py:342:@router.patch(
apps/api/app/api\admin_stage_gates.py:350:    principal: Principal = Depends(require_permission("admin.stage_gates")),
apps/api/app/api\admin_stage_gates.py:351:    session: Session = Depends(get_db),
apps/api/app/api\admin_stage_gates.py:437:@router.post("/stage-gates/reorder", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
apps/api/app/api\admin_stage_gates.py:440:    principal: Principal = Depends(require_permission("admin.stage_gates")),
apps/api/app/api\admin_stage_gates.py:441:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:128:@router.get("", tags=["formulations"])
apps/api/app/api\formulations.py:131:    principal: Principal = Depends(require_permission("formula.view")),
apps/api/app/api\formulations.py:132:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:137:@router.post("", status_code=status.HTTP_201_CREATED, tags=["formulations"])
apps/api/app/api\formulations.py:140:    principal: Principal = Depends(require_permission("formula.create")),
apps/api/app/api\formulations.py:141:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:174:@router.get("/versions/{version_id}", tags=["formulations"])
apps/api/app/api\formulations.py:177:    principal: Principal = Depends(require_permission("formula.view")),
apps/api/app/api\formulations.py:178:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:194:@router.put("/versions/{version_id}/components", tags=["formulations"])
apps/api/app/api\formulations.py:198:    principal: Principal = Depends(require_permission("formula.modify_draft")),
apps/api/app/api\formulations.py:199:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:233:@router.get("/versions/{version_id}/evaluation", tags=["formulations"])
apps/api/app/api\formulations.py:236:    principal: Principal = Depends(require_permission("formula.view")),
apps/api/app/api\formulations.py:237:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:257:@router.post("/versions/{version_id}/weigh-up", tags=["formulations"])
apps/api/app/api\formulations.py:261:    principal: Principal = Depends(require_permission("formula.view")),
apps/api/app/api\formulations.py:262:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:278:@router.post("/versions/{version_id}/submission", tags=["formulations"])
apps/api/app/api\formulations.py:281:    principal: Principal = Depends(require_permission("formula.submit")),
apps/api/app/api\formulations.py:282:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:308:@router.post("/versions/{version_id}/decision", tags=["formulations"])
apps/api/app/api\formulations.py:312:    principal: Principal = Depends(require_permission("formula.approve_lab")),
apps/api/app/api\formulations.py:313:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:338:@router.post(
apps/api/app/api\formulations.py:344:    principal: Principal = Depends(require_permission("formula.clone")),
apps/api/app/api\formulations.py:345:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:372:@router.post("/versions/{version_id}/observed-effect", tags=["formulations"])
apps/api/app/api\formulations.py:376:    principal: Principal = Depends(require_permission("formula.clone", "formula.modify_draft")),
apps/api/app/api\formulations.py:377:    session: Session = Depends(get_db),
apps/api/app/api\formulations.py:398:@router.get("/versions/{version_id}/comparison", tags=["formulations"])
apps/api/app/api\formulations.py:402:    principal: Principal = Depends(require_permission("formula.view")),
apps/api/app/api\formulations.py:403:    session: Session = Depends(get_db),
apps/api/app/api\admin_reference_data.py:126:@router.get("/units", tags=["administration"])
apps/api/app/api\admin_reference_data.py:129:    principal: Principal = Depends(require_permission("admin.reference_data", "material.view")),
apps/api/app/api\admin_reference_data.py:130:    session: Session = Depends(get_db),
apps/api/app/api\admin_reference_data.py:153:@router.post("/units", status_code=status.HTTP_201_CREATED, tags=["administration"])
apps/api/app/api\admin_reference_data.py:156:    principal: Principal = Depends(require_permission("admin.reference_data")),
apps/api/app/api\admin_reference_data.py:157:    session: Session = Depends(get_db),
apps/api/app/api\admin_reference_data.py:198:@router.get("/product-families", tags=["administration"])
apps/api/app/api\admin_reference_data.py:201:    principal: Principal = Depends(require_permission("admin.reference_data", "material.view")),
apps/api/app/api\admin_reference_data.py:202:    session: Session = Depends(get_db),
apps/api/app/api\admin_reference_data.py:218:@router.post("/product-families", status_code=status.HTTP_201_CREATED, tags=["administration"])
apps/api/app/api\admin_reference_data.py:221:    principal: Principal = Depends(require_permission("admin.reference_data")),
apps/api/app/api\admin_reference_data.py:222:    session: Session = Depends(get_db),
apps/api/app/api\admin_reference_data.py:263:@router.patch("/{collection}/{item_id}", tags=["administration"])
apps/api/app/api\admin_reference_data.py:268:    principal: Principal = Depends(require_permission("admin.reference_data")),
apps/api/app/api\admin_reference_data.py:269:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:96:@router.get("", tags=["my-work"])
apps/api/app/api\tasks.py:99:    principal: Principal = Depends(get_principal),
apps/api/app/api\tasks.py:100:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:112:@router.get("/counts", tags=["my-work"])
apps/api/app/api\tasks.py:114:    principal: Principal = Depends(get_principal),
apps/api/app/api\tasks.py:115:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:130:@router.post("", status_code=status.HTTP_201_CREATED, tags=["my-work"])
apps/api/app/api\tasks.py:133:    principal: Principal = Depends(require_permission("project.edit")),
apps/api/app/api\tasks.py:134:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:164:@router.post("/{task_id}/claim", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
apps/api/app/api\tasks.py:167:    principal: Principal = Depends(get_principal),
apps/api/app/api\tasks.py:168:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:188:@router.post("/{task_id}/complete", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
apps/api/app/api\tasks.py:192:    principal: Principal = Depends(get_principal),
apps/api/app/api\tasks.py:193:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:210:@router.post("/{task_id}/reassign", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
apps/api/app/api\tasks.py:214:    principal: Principal = Depends(require_permission("project.edit")),
apps/api/app/api\tasks.py:215:    session: Session = Depends(get_db),
apps/api/app/api\tasks.py:235:@router.get("/project/{project_id}", tags=["my-work"])
apps/api/app/api\tasks.py:238:    principal: Principal = Depends(require_permission("project.view")),
apps/api/app/api\tasks.py:239:    _scope: Principal = Depends(require_project_member("project_id")),
apps/api/app/api\tasks.py:240:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:192:@router.get("", tags=["failures"])
apps/api/app/api\failures.py:196:    principal: Principal = Depends(require_permission("failure.view")),
apps/api/app/api\failures.py:197:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:213:@router.post("", status_code=status.HTTP_201_CREATED, tags=["failures"])
apps/api/app/api\failures.py:216:    principal: Principal = Depends(require_permission("failure.create")),
apps/api/app/api\failures.py:217:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:241:@router.get("/{failure_id}", tags=["failures"])
apps/api/app/api\failures.py:244:    principal: Principal = Depends(require_permission("failure.view")),
apps/api/app/api\failures.py:245:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:262:@router.post("/{failure_id}/hypotheses", status_code=status.HTTP_201_CREATED, tags=["failures"])
apps/api/app/api\failures.py:266:    principal: Principal = Depends(require_permission("failure.investigate")),
apps/api/app/api\failures.py:267:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:290:@router.post("/{failure_id}/evidence", status_code=status.HTTP_201_CREATED, tags=["failures"])
apps/api/app/api\failures.py:294:    principal: Principal = Depends(require_permission("failure.investigate")),
apps/api/app/api\failures.py:295:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:310:@router.post(
apps/api/app/api\failures.py:319:    principal: Principal = Depends(require_permission("failure.investigate")),
apps/api/app/api\failures.py:320:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:344:@router.post("/{failure_id}/root-cause", tags=["failures"])
apps/api/app/api\failures.py:348:    principal: Principal = Depends(require_permission("failure.accept_root_cause")),
apps/api/app/api\failures.py:349:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:373:@router.post("/{failure_id}/hypotheses/{hypothesis_id}/rejection", tags=["failures"])
apps/api/app/api\failures.py:378:    principal: Principal = Depends(require_permission("failure.investigate")),
apps/api/app/api\failures.py:379:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:396:@router.post("/{failure_id}/actions", status_code=status.HTTP_201_CREATED, tags=["failures"])
apps/api/app/api\failures.py:400:    principal: Principal = Depends(require_permission("failure.investigate")),
apps/api/app/api\failures.py:401:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:418:@router.post("/{failure_id}/closure", tags=["failures"])
apps/api/app/api\failures.py:422:    principal: Principal = Depends(require_permission("failure.close")),
apps/api/app/api\failures.py:423:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:451:@approvals_router.get("/queue", tags=["approvals"])
apps/api/app/api\failures.py:453:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api\failures.py:454:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:473:@approvals_router.post("", status_code=status.HTTP_201_CREATED, tags=["approvals"])
apps/api/app/api\failures.py:476:    principal: Principal = Depends(require_permission("test.plan", "formula.submit")),
apps/api/app/api\failures.py:477:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:498:@approvals_router.get("/{route_id}", tags=["approvals"])
apps/api/app/api\failures.py:501:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api\failures.py:502:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:516:@approvals_router.get("/entity/{entity_type}/{entity_id}", tags=["approvals"])
apps/api/app/api\failures.py:520:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api\failures.py:521:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:536:@approvals_router.post("/{route_id}/steps/{step_id}/decision", tags=["approvals"])
apps/api/app/api\failures.py:541:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api\failures.py:542:    session: Session = Depends(get_db),
apps/api/app/api\failures.py:583:@approvals_router.post(
apps/api/app/api\failures.py:591:    principal: Principal = Depends(require_permission("formula.clone", "formula.create")),
apps/api/app/api\failures.py:592:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:98:@router.get("/permissions", response_model=list[PermissionRead], tags=["admin"])
apps/api/app/api\admin.py:100:    _: Principal = Depends(require_permission("admin.roles")),
apps/api/app/api\admin.py:101:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:121:@router.get("/roles", response_model=list[RoleRead], tags=["admin"])
apps/api/app/api\admin.py:123:    _: Principal = Depends(require_permission("admin.roles")),
apps/api/app/api\admin.py:124:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:148:@router.get("/members", response_model=list[MemberRead], tags=["admin"])
apps/api/app/api\admin.py:150:    principal: Principal = Depends(require_permission("admin.users")),
apps/api/app/api\admin.py:151:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:180:@router.post(
apps/api/app/api\admin.py:188:    principal: Principal = Depends(require_permission("admin.users")),
apps/api/app/api\admin.py:189:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:266:@router.post("/members/{member_id}/roles", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
apps/api/app/api\admin.py:270:    principal: Principal = Depends(require_permission("admin.roles")),
apps/api/app/api\admin.py:271:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:308:@router.delete(
apps/api/app/api\admin.py:317:    principal: Principal = Depends(require_permission("admin.roles")),
apps/api/app/api\admin.py:318:    session: Session = Depends(get_db),
apps/api/app/api\admin.py:367:@router.patch("/members/{member_id}/status", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
apps/api/app/api\admin.py:371:    principal: Principal = Depends(require_permission("admin.users")),
apps/api/app/api\admin.py:372:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:77:@router.get("/channels", summary="Channels this user can see")
apps/api/app/api\messaging.py:79:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:80:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:91:@router.post("/channels", status_code=status.HTTP_201_CREATED, summary="Open a channel")
apps/api/app/api\messaging.py:94:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:95:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:119:@router.post("/threads", summary="The discussion thread for a record, opening one if needed")
apps/api/app/api\messaging.py:122:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:123:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:147:@router.get("/channels/{channel_id}/messages", summary="A channel's messages")
apps/api/app/api\messaging.py:150:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:151:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:162:@router.post(
apps/api/app/api\messaging.py:170:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:171:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:189:@router.post(
apps/api/app/api\messaging.py:197:    principal: Principal = Depends(require_permission("project.edit")),
apps/api/app/api\messaging.py:198:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:225:@router.get("/notifications", summary="This user's notifications")
apps/api/app/api\messaging.py:227:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:228:    session: Session = Depends(get_db),
apps/api/app/api\messaging.py:241:@router.post("/notifications/{notification_id}/read", summary="Mark one as read")
apps/api/app/api\messaging.py:244:    principal: Principal = Depends(get_principal),
apps/api/app/api\messaging.py:245:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:193:@router.get("", tags=["materials"])
apps/api/app/api\materials.py:198:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api\materials.py:199:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:211:@router.post("", status_code=status.HTTP_201_CREATED, tags=["materials"])
apps/api/app/api\materials.py:214:    principal: Principal = Depends(require_permission("material.create")),
apps/api/app/api\materials.py:215:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:233:@router.get("/{material_id}", tags=["materials"])
apps/api/app/api\materials.py:236:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api\materials.py:237:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:247:@router.put("/{material_id}", tags=["materials"])
apps/api/app/api\materials.py:251:    principal: Principal = Depends(require_permission("material.edit")),
apps/api/app/api\materials.py:252:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:276:@router.post("/{material_id}/status", tags=["materials"])
apps/api/app/api\materials.py:280:    principal: Principal = Depends(get_principal),
apps/api/app/api\materials.py:281:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:318:@router.get("/{material_id}/usage", tags=["materials"])
apps/api/app/api\materials.py:321:    principal: Principal = Depends(
apps/api/app/api\materials.py:331:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:345:@router.get("/{material_id}/documents", tags=["materials"])
apps/api/app/api\materials.py:348:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api\materials.py:349:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:357:@router.post("/{material_id}/documents", status_code=status.HTTP_201_CREATED, tags=["materials"])
apps/api/app/api\materials.py:361:    principal: Principal = Depends(require_permission("material.edit", "supplier.manage")),
apps/api/app/api\materials.py:362:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:391:@router.post("/{material_id}/suppliers", status_code=status.HTTP_201_CREATED, tags=["materials"])
apps/api/app/api\materials.py:395:    principal: Principal = Depends(require_permission("supplier.manage")),
apps/api/app/api\materials.py:396:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:419:@suppliers_router.get("", tags=["suppliers"])
apps/api/app/api\materials.py:422:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api\materials.py:423:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:435:@suppliers_router.post("", status_code=status.HTTP_201_CREATED, tags=["suppliers"])
apps/api/app/api\materials.py:438:    principal: Principal = Depends(require_permission("supplier.manage")),
apps/api/app/api\materials.py:439:    session: Session = Depends(get_db),
apps/api/app/api\materials.py:455:@suppliers_router.post("/{supplier_id}/status", tags=["suppliers"])
apps/api/app/api\materials.py:459:    principal: Principal = Depends(require_permission("supplier.manage")),
apps/api/app/api\materials.py:460:    session: Session = Depends(get_db),
apps/api/app/api\me.py:88:@router.get("", response_model=Me, tags=["identity"])
apps/api/app/api\me.py:89:async def read_me(subject: Annotated[str, Depends(get_verified_subject)]) -> Me:
apps/api/app/api\projects.py:149:@router.get("", response_model=list[ProjectSummary], tags=["projects"])
apps/api/app/api\projects.py:151:    principal: Principal = Depends(require_permission("project.view")),
apps/api/app/api\projects.py:152:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:178:@router.post(
apps/api/app/api\projects.py:183:    principal: Principal = Depends(require_permission("project.create")),
apps/api/app/api\projects.py:184:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:245:@router.get("/{project_id}", response_model=ProjectSummary, tags=["projects"])
apps/api/app/api\projects.py:248:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:249:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:271:@router.get("/{project_id}/dashboard", tags=["projects"])
apps/api/app/api\projects.py:274:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:275:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:298:@router.get("/{project_id}/pipeline", tags=["pipeline"])
apps/api/app/api\projects.py:301:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:302:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:310:@router.get("/{project_id}/pipeline/history", tags=["pipeline"])
apps/api/app/api\projects.py:313:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:314:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:325:@router.post("/{project_id}/pipeline/advance", tags=["pipeline"])
apps/api/app/api\projects.py:329:    principal: Principal = Depends(require_permission("project.advance_stage")),
apps/api/app/api\projects.py:330:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:331:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:368:@router.get("/{project_id}/requirements/matrix", tags=["requirements"])
apps/api/app/api\projects.py:371:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:372:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:379:@router.post(
apps/api/app/api\projects.py:385:    principal: Principal = Depends(require_permission("requirement.create")),
apps/api/app/api\projects.py:386:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:387:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:404:@router.post(
apps/api/app/api\projects.py:412:    principal: Principal = Depends(require_permission("requirement.approve")),
apps/api/app/api\projects.py:413:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:414:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:429:@router.post(
apps/api/app/api\projects.py:438:    principal: Principal = Depends(require_permission("requirement.create")),
apps/api/app/api\projects.py:439:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:440:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:520:@router.get("/{project_id}/milestones", tags=["projects"])
apps/api/app/api\projects.py:523:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:524:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:534:@router.post("/{project_id}/milestones", status_code=status.HTTP_201_CREATED, tags=["projects"])
apps/api/app/api\projects.py:538:    principal: Principal = Depends(require_permission("milestone.manage")),
apps/api/app/api\projects.py:539:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:540:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:556:@router.patch("/{project_id}/milestones/{milestone_id}/status", tags=["projects"])
apps/api/app/api\projects.py:561:    principal: Principal = Depends(require_permission("milestone.manage")),
apps/api/app/api\projects.py:562:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:563:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:588:@router.get("/{project_id}/risks", tags=["projects"])
apps/api/app/api\projects.py:591:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:592:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:602:@router.post("/{project_id}/risks", status_code=status.HTTP_201_CREATED, tags=["projects"])
apps/api/app/api\projects.py:606:    principal: Principal = Depends(require_permission("risk.create")),
apps/api/app/api\projects.py:607:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:608:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:638:@router.patch("/{project_id}/risks/{risk_id}", tags=["projects"])
apps/api/app/api\projects.py:643:    principal: Principal = Depends(require_permission("risk.manage")),
apps/api/app/api\projects.py:644:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:645:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:690:@router.get("/{project_id}/members", tags=["projects"])
apps/api/app/api\projects.py:693:    principal: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:694:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:704:@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED, tags=["projects"])
apps/api/app/api\projects.py:708:    principal: Principal = Depends(require_permission("project.assign_member")),
apps/api/app/api\projects.py:709:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:710:    session: Session = Depends(get_db),
apps/api/app/api\projects.py:727:@router.post(
apps/api/app/api\projects.py:736:    principal: Principal = Depends(require_permission("project.assign_member")),
apps/api/app/api\projects.py:737:    _member: Principal = Depends(require_project_member()),
apps/api/app/api\projects.py:738:    session: Session = Depends(get_db),
apps/api/app/api\opportunities.py:76:@router.get("", tags=["opportunities"])
apps/api/app/api\opportunities.py:79:    principal: Principal = Depends(require_permission("opportunity.view")),
apps/api/app/api\opportunities.py:80:    session: Session = Depends(get_db),
apps/api/app/api\opportunities.py:88:@router.post("", status_code=status.HTTP_201_CREATED, tags=["opportunities"])
apps/api/app/api\opportunities.py:91:    principal: Principal = Depends(require_permission("opportunity.create")),
apps/api/app/api\opportunities.py:92:    session: Session = Depends(get_db),
apps/api/app/api\opportunities.py:106:@router.get("/{opportunity_id}", tags=["opportunities"])
apps/api/app/api\opportunities.py:109:    principal: Principal = Depends(require_permission("opportunity.view")),
apps/api/app/api\opportunities.py:110:    session: Session = Depends(get_db),
apps/api/app/api\opportunities.py:122:@router.post("/{opportunity_id}/decision", tags=["opportunities"])
apps/api/app/api\opportunities.py:126:    principal: Principal = Depends(require_permission("opportunity.decide")),
apps/api/app/api\opportunities.py:127:    session: Session = Depends(get_db),
apps/api/app/api\opportunities.py:150:@router.post(
apps/api/app/api\opportunities.py:162:    principal: Principal = Depends(require_permission("project.create")),
apps/api/app/api\opportunities.py:163:    session: Session = Depends(get_db),
apps/api/app\main.py:88:        allow_origins=settings.cors_allowed_origins,
apps/api/app\main.py:177:    # a valid token and no way to discover a tenant to ask for. See
apps/api/migrations\024_memberships_for_subject.sql:14:-- So a browser that has just signed in holds a valid token and has NO
apps/api/migrations\024_memberships_for_subject.sql:39:-- `unscoped_session_scope()`'s own docstring states that end state
apps/api/migrations\024_memberships_for_subject.sql:57:--   * It is scoped to `p_sub`, which is the `sub` claim of a token whose
apps/api/migrations\024_memberships_for_subject.sql:60:--     forging a token the realm's JWKS would have to sign.
render.yaml:13:# against the Render API, because the API key is a GitHub Actions secret and
apps/api/migrations\013_audit_policy_and_definer_hardening.sql:38:--    `unscoped_session_scope()` is used in exactly three places -- the
apps/api/migrations\011_audit_chain_per_organization.sql:52:--      a maintenance script, anything using unscoped_session_scope() --
apps/api/migrations\001_core_tenancy.sql:212:    -- Keycloak owns credentials; there is deliberately no password column.
apps/api/app\domains\formulations\service.py:476:            # logging and a formulation IS the secret this product exists
apps/api/app\domains\materials\service.py:31:actor ids come from a verified token and are never client-supplied -- but
apps/api/app\domains\msd\retrieval.py:24:CALLER'S OWN SESSION, whose RLS GUCs were set from their verified token,
apps/api/app\domains\msd\retrieval.py:184:    from the caller's verified token, so PostgreSQL returns exactly the
apps/api/app\core\config.py:4:-- a missing database password should stop the process at startup, not
apps/api/app\core\config.py:8:from a committed file. Note for anyone writing a secrets file on this
apps/api/app\core\config.py:10:unparseable in a way that looks like a wrong password. Write UTF-8
apps/api/app\core\config.py:59:    garage_secret_key: str | None = None
apps/api/app\core\audit.py:69:    compositions in full, secrets or tokens -- SECURITY.md §11 forbids
apps/api/app\core\logging.py:10:percentages, secrets, tokens, or full request bodies from formulation
apps/api/app\core\logging.py:52:        "password",
apps/api/app\core\logging.py:53:        "secret",
apps/api/app\core\logging.py:54:        "token",
apps/api/app\core\logging.py:55:        "access_token",
apps/api/app\core\logging.py:56:        "refresh_token",
apps/api/app\core\logging.py:59:        "client_secret",
apps/api/app\core\security.py:138:async def _decode(token: str) -> dict[str, Any]:
apps/api/app\core\security.py:145:            token,
apps/api/app\core\security.py:161:            detail="invalid token",
apps/api/app\core\security.py:198:    """The token's subject, with no organization required.
apps/api/app\core\security.py:206:    depends on it, so a browser that had just signed in held a valid token
apps/api/app\core\security.py:224:            detail="missing bearer token",
apps/api/app\core\security.py:230:        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")
apps/api/app\core\security.py:241:    trusted from the token's claims. A JWT is a statement about identity;
apps/api/app\core\security.py:243:    membership must take effect immediately, not when the access token
apps/api/app\core\security.py:249:            detail="missing bearer token",
apps/api/app\core\security.py:257:        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")
apps/api/app\core\security.py:281:    from app.core.db import unscoped_session_scope
apps/api/app\core\security.py:283:    with unscoped_session_scope() as session:
apps/api/app\core\db.py:52:    "unscoped_session_scope",
apps/api/app\core\db.py:209:            ``allow_unscoped=True`` via :func:`unscoped_session_scope`.
apps/api/app\core\db.py:218:            "use unscoped_session_scope() and justify it in review."
apps/api/app\core\db.py:235:def unscoped_session_scope() -> Iterator[Session]:
.env.example:10:# wrong password. Write UTF-8 explicitly:
apps/api/app\api\health.py:29:from app.core.db import unscoped_session_scope
apps/api/app\api\health.py:46:        with unscoped_session_scope() as session:
apps/api/app\api\health.py:65:        with unscoped_session_scope() as session:
apps/api/app\api\me.py:12:So a browser that had just signed in held a perfectly valid token and
apps/api/app\api\me.py:53:from app.core.db import unscoped_session_scope
apps/api/app\api\me.py:102:    genuine token carries a UUID. The subject then resolves to no row,
apps/api/app\api\me.py:108:    # unscoped_session_scope() rather than get_db(), and named ugly on
apps/api/app\api\me.py:115:    with unscoped_session_scope() as session:
apps/api/app\api\me.py:122:                "this token is valid, but its subject matches no active user with "
apps/api/app\api\messaging.py:247:    """`recipient_id` comes from the token, never the request.
apps/api/app\api\tasks.py:8:`principal.roles`, both of which come from a signature-verified token and
infrastructure\compose\garage.toml:25:rpc_secret = "0000000000000000000000000000000000000000000000000000000000000000"
infrastructure\compose\garage.toml:41:admin_token   = "0000000000000000000000000000000000000000000="

2026-08-20T19:13:43.081820Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files=@('"'apps/api/app/core/security.py','apps/api/app/core/config.py','apps/api/app/main.py','apps/api/app/api/health.py','apps/api/app/api/testing.py','apps/api/app/api/laboratory.py','apps/api/app/api/materials.py','apps/api/app/core/logging.py'); foreach("'$f in $files){Write-Output "FILE $f"; $n=1; Get-Content $f | ForEach-Object {"$n`t$_"; $n++}}'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files=@('"'apps/api/app/core/security.py','apps/api/app/core/config.py','apps/api/app/main.py','apps/api/app/api/health.py','apps/api/app/api/testing.py','apps/api/app/api/laboratory.py','apps/api/app/api/materials.py','apps/api/app/core/logging.py'); foreach("'$f in $files){Write-Output "FILE $f"; $n=1; Get-Content $f | ForEach-Object {"$n`t$_"; $n++}}' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files=@('"'apps/api/app/core/security.py','apps/api/app/core/config.py','apps/api/app/main.py','apps/api/app/api/health.py','apps/api/app/api/testing.py','apps/api/app/api/laboratory.py','apps/api/app/api/materials.py','apps/api/app/core/logging.py'); foreach("'$f in $files){Write-Output "FILE $f"; $n=1; Get-Content $f | ForEach-Object {"$n`t$_"; $n++}}'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "." apps/api/app/core/security.py apps/api/app/core/config.py apps/api/app/main.py apps/api/app/api/health.py apps/api/app/core/logging.py' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 320ms:
apps/api/app/api/health.py:1:"""Health endpoints.
apps/api/app/api/health.py:3:Three, because they answer three different questions and conflating them
apps/api/app/api/health.py:4:causes real outages:
apps/api/app/api/health.py:6:``/health/live``   Is the process running? Never touches a dependency, so
apps/api/app/api/health.py:7:                   a database blip cannot get the container killed and
apps/api/app/api/health.py:8:                   restarted into the same blip.
apps/api/app/api/health.py:9:``/health/ready``  Can it serve traffic? Checks dependencies. This is what
apps/api/app/api/health.py:10:                   compose and any load balancer should probe.
apps/api/app/api/health.py:11:``/health/startup`` Has first-time initialisation finished? Distinguishes
apps/api/app/api/health.py:12:                   "still booting" from "broken" during the ~2 minute
apps/api/app/api/health.py:13:                   cold starts a free tier can produce -- a short timeout
apps/api/app/api/health.py:14:                   against a cold start is not proof of an outage.
apps/api/app/api/health.py:16:Deliberately unauthenticated, and deliberately thin: a health endpoint
apps/api/app/api/health.py:17:that enumerates versions or connection strings is reconnaissance.
apps/api/app/api/health.py:18:"""
apps/api/app/api/health.py:20:from __future__ import annotations
apps/api/app/api/health.py:22:import time
apps/api/app/api/health.py:23:from typing import Any, Literal
apps/api/app/api/health.py:25:import structlog
apps/api/app/api/health.py:26:from fastapi import APIRouter, Response, status
apps/api/app/api/health.py:27:from sqlalchemy import text
apps/api/app/api/health.py:29:from app.core.db import unscoped_session_scope
apps/api/app/api/health.py:31:router = APIRouter()
apps/api/app/api/health.py:32:log = structlog.get_logger(__name__)
apps/api/app/api/health.py:34:_STARTED_AT = time.monotonic()
apps/api/app/api/health.py:36:__all__ = ["router"]
apps/api/app/api/health.py:39:@router.get("/live", include_in_schema=False)
apps/api/app/api/health.py:40:async def live() -> dict[str, str]:
apps/api/app/api/health.py:41:    return {"status": "alive"}
apps/api/app/api/health.py:44:def _check_database() -> tuple[bool, str]:
apps/api/app/api/health.py:45:    try:
apps/api/app/api/health.py:46:        with unscoped_session_scope() as session:
apps/api/app/api/health.py:47:            session.execute(text("SELECT 1"))
apps/api/app/api/health.py:48:        return True, "ok"
apps/api/app/api/health.py:49:    except Exception as exc:  # noqa: BLE001
apps/api/app/api/health.py:50:        # Log the reason; do not return it. The exception text can contain
apps/api/app/api/health.py:51:        # host names, role names and connection details.
apps/api/app/api/health.py:52:        log.warning("health_database_unavailable", error=str(exc))
apps/api/app/api/health.py:53:        return False, "unavailable"
apps/api/app/api/health.py:56:def _check_migrations() -> tuple[bool, str]:
apps/api/app/api/health.py:57:    """Confirm the tenancy foundation is actually present.
apps/api/app/api/health.py:59:    A database that answers SELECT 1 but has no RLS is *worse* than one
apps/api/app/api/health.py:60:    that is down: it serves requests with no tenant isolation. Readiness
apps/api/app/api/health.py:61:    therefore checks that the context helper exists, not merely that a
apps/api/app/api/health.py:62:    connection can be made.
apps/api/app/api/health.py:63:    """
apps/api/app/api/health.py:64:    try:
apps/api/app/api/health.py:65:        with unscoped_session_scope() as session:
apps/api/app/api/health.py:66:            found = session.execute(
apps/api/app/api/health.py:67:                text(
apps/api/app/api/health.py:68:                    """
apps/api/app/api/health.py:69:                    SELECT EXISTS (
apps/api/app/api/health.py:70:                        SELECT 1 FROM pg_proc p
apps/api/app/api/health.py:71:                        JOIN pg_namespace n ON n.oid = p.pronamespace
apps/api/app/api/health.py:72:                        WHERE n.nspname = 'core' AND p.proname = 'current_org_id'
apps/api/app/api/health.py:73:                    )
apps/api/app/api/health.py:74:                    """
apps/api/app/api/health.py:75:                )
apps/api/app/api/health.py:76:            ).scalar_one()
apps/api/app/api/health.py:77:        return bool(found), "ok" if found else "migrations not applied"
apps/api/app/api/health.py:78:    except Exception as exc:  # noqa: BLE001
apps/api/app/api/health.py:79:        log.warning("health_migration_check_failed", error=str(exc))
apps/api/app/api/health.py:80:        return False, "unavailable"
apps/api/app/api/health.py:83:@router.get("/ready", include_in_schema=False)
apps/api/app/api/health.py:84:async def ready(response: Response) -> dict[str, Any]:
apps/api/app/api/health.py:85:    checks: dict[str, str] = {}
apps/api/app/api/health.py:87:    db_ok, checks["database"] = _check_database()
apps/api/app/api/health.py:88:    mig_ok, checks["migrations"] = _check_migrations()
apps/api/app/api/health.py:90:    healthy = db_ok and mig_ok
apps/api/app/api/health.py:91:    if not healthy:
apps/api/app/api/health.py:92:        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
apps/api/app/api/health.py:94:    return {"status": "ready" if healthy else "not_ready", "checks": checks}
apps/api/app/api/health.py:97:@router.get("/startup", include_in_schema=False)
apps/api/app/api/health.py:98:async def startup(response: Response) -> dict[str, Any]:
apps/api/app/api/health.py:99:    db_ok, _ = _check_database()
apps/api/app/api/health.py:100:    uptime = round(time.monotonic() - _STARTED_AT, 1)
apps/api/app/api/health.py:102:    state: Literal["starting", "started"] = "started" if db_ok else "starting"
apps/api/app/api/health.py:103:    if not db_ok:
apps/api/app/api/health.py:104:        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
apps/api/app/api/health.py:106:    return {"status": state, "uptime_seconds": uptime}
apps/api/app/core/security.py:1:"""Authentication and authorization.
apps/api/app/core/security.py:2:
apps/api/app/core/security.py:3:Implements the chain from CLAUDE.md §6, enforced in this order on every
apps/api/app/core/security.py:4:request:
apps/api/app/core/security.py:5:
apps/api/app/core/security.py:6:    Authentication -> Organization -> Role -> Permission
apps/api/app/core/security.py:7:                   -> Resource Scope -> Business Rule
apps/api/app/core/security.py:8:
apps/api/app/core/security.py:9:with PostgreSQL RLS as an independent database-layer backstop.
apps/api/app/core/security.py:10:
apps/api/app/core/security.py:11:Two rules govern everything here.
apps/api/app/core/security.py:12:
apps/api/app/core/security.py:13:**Authorize on permissions, never on role names.** A role is a seeded
apps/api/app/core/security.py:14:bundle. Checking ``role == "qa_compliance_officer"`` cannot express "QA
apps/api/app/core/security.py:15:approval may not come from someone who supplied a development-side
apps/api/app/core/security.py:16:approval on this same test" (ADR-019), and it hard-codes a deployment's
apps/api/app/core/security.py:17:staffing into the application. Permissions are data; roles are defaults.
apps/api/app/core/security.py:18:
apps/api/app/core/security.py:19:**Resource scope is a separate check from permission.** Holding
apps/api/app/core/security.py:20:``test.review`` does not grant review of a test in a project you are not
apps/api/app/core/security.py:21:a member of. These are different questions and conflating them is how
apps/api/app/core/security.py:22:intra-organization confidentiality gets lost -- the defect that made the
apps/api/app/core/security.py:23:original three-layer claim false (Codex F32).
apps/api/app/core/security.py:24:
apps/api/app/core/security.py:25:Frontend permission checks are cosmetic. Everything is re-enforced here.
apps/api/app/core/security.py:26:"""
apps/api/app/core/security.py:27:
apps/api/app/core/security.py:28:from __future__ import annotations
apps/api/app/core/security.py:29:
apps/api/app/core/security.py:30:import time
apps/api/app/core/security.py:31:import uuid
apps/api/app/core/security.py:32:from collections.abc import Callable, Iterator
apps/api/app/core/security.py:33:from dataclasses import dataclass, field
apps/api/app/core/security.py:34:from typing import Any
apps/api/app/core/security.py:35:
apps/api/app/core/security.py:36:import httpx
apps/api/app/core/security.py:37:from fastapi import Depends, HTTPException, Request, status
apps/api/app/core/security.py:38:from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
apps/api/app/core/security.py:39:from jose import JWTError, jwt
apps/api/app/core/security.py:40:from sqlalchemy import text
apps/api/app/core/security.py:41:from sqlalchemy.orm import Session
apps/api/app/core/security.py:42:
apps/api/app/core/security.py:43:from app.core.config import settings
apps/api/app/core/security.py:44:from app.core.db import RequestContext, session_scope
apps/api/app/core/security.py:45:
apps/api/app/core/security.py:46:__all__ = [
apps/api/app/core/security.py:47:    "PermissionDenied",
apps/api/app/core/security.py:48:    "Principal",
apps/api/app/core/security.py:49:    "get_db",
apps/api/app/core/security.py:50:    "get_principal",
apps/api/app/core/security.py:51:    "require_permission",
apps/api/app/core/security.py:52:    "require_project_member",
apps/api/app/core/security.py:53:]
apps/api/app/core/security.py:54:
apps/api/app/core/security.py:55:_bearer = HTTPBearer(auto_error=False)
apps/api/app/core/security.py:56:
apps/api/app/core/security.py:57:
apps/api/app/core/security.py:58:class PermissionDenied(HTTPException):
apps/api/app/core/security.py:59:    """403 with a stable shape.
apps/api/app/core/security.py:60:
apps/api/app/core/security.py:61:    The detail deliberately does not say whether the resource exists.
apps/api/app/core/security.py:62:    "You may not see it" and "it does not exist" must be indistinguishable
apps/api/app/core/security.py:63:    to the caller, or the error message itself becomes a discovery channel
apps/api/app/core/security.py:64:    for other teams' project codes.
apps/api/app/core/security.py:65:    """
apps/api/app/core/security.py:66:
apps/api/app/core/security.py:67:    def __init__(self, detail: str = "Not permitted") -> None:
apps/api/app/core/security.py:68:        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
apps/api/app/core/security.py:69:
apps/api/app/core/security.py:70:
apps/api/app/core/security.py:71:@dataclass(frozen=True, slots=True)
apps/api/app/core/security.py:72:class Principal:
apps/api/app/core/security.py:73:    """The verified caller.
apps/api/app/core/security.py:74:
apps/api/app/core/security.py:75:    Every field here comes from a signature-verified JWT or from the
apps/api/app/core/security.py:76:    database. Nothing is taken from a header, query parameter or request
apps/api/app/core/security.py:77:    body -- a client-supplied organization id would make the entire
apps/api/app/core/security.py:78:    tenancy model advisory.
apps/api/app/core/security.py:79:    """
apps/api/app/core/security.py:80:
apps/api/app/core/security.py:81:    user_id: uuid.UUID
apps/api/app/core/security.py:82:    organization_id: uuid.UUID
apps/api/app/core/security.py:83:    keycloak_sub: str
apps/api/app/core/security.py:84:    email: str
apps/api/app/core/security.py:85:    display_name: str
apps/api/app/core/security.py:86:    roles: frozenset[str] = field(default_factory=frozenset)
apps/api/app/core/security.py:87:    permissions: frozenset[str] = field(default_factory=frozenset)
apps/api/app/core/security.py:88:    session_id: str | None = None
apps/api/app/core/security.py:89:
apps/api/app/core/security.py:90:    @property
apps/api/app/core/security.py:91:    def context(self) -> RequestContext:
apps/api/app/core/security.py:92:        return RequestContext(organization_id=self.organization_id, user_id=self.user_id)
apps/api/app/core/security.py:93:
apps/api/app/core/security.py:94:    def has(self, permission: str) -> bool:
apps/api/app/core/security.py:95:        return permission in self.permissions
apps/api/app/core/security.py:96:
apps/api/app/core/security.py:97:
apps/api/app/core/security.py:98:# ---------------------------------------------------------------------------
apps/api/app/core/security.py:99:# JWKS
apps/api/app/core/security.py:100:# ---------------------------------------------------------------------------
apps/api/app/core/security.py:101:
apps/api/app/core/security.py:102:_jwks_cache: dict[str, Any] = {}
apps/api/app/core/security.py:103:_jwks_fetched_at: float = 0.0
apps/api/app/core/security.py:104:
apps/api/app/core/security.py:105:
apps/api/app/core/security.py:106:async def _get_jwks() -> dict[str, Any]:
apps/api/app/core/security.py:107:    """Fetch and cache the realm's signing keys.
apps/api/app/core/security.py:108:
apps/api/app/core/security.py:109:    The cache is bounded by ``jwks_cache_seconds`` because that window is
apps/api/app/core/security.py:110:    how long a rotated-out signing key stays trusted. On a fetch failure
apps/api/app/core/security.py:111:    we keep serving the previous keys rather than failing every request --
apps/api/app/core/security.py:112:    a Keycloak blip should not take the API down -- but we never extend
apps/api/app/core/security.py:113:    the window silently past a successful refresh.
apps/api/app/core/security.py:114:    """
apps/api/app/core/security.py:115:    global _jwks_cache, _jwks_fetched_at
apps/api/app/core/security.py:116:
apps/api/app/core/security.py:117:    age = time.monotonic() - _jwks_fetched_at
apps/api/app/core/security.py:118:    if _jwks_cache and age < settings.jwks_cache_seconds:
apps/api/app/core/security.py:119:        return _jwks_cache
apps/api/app/core/security.py:120:
apps/api/app/core/security.py:121:    url = f"{settings.keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"
apps/api/app/core/security.py:122:    try:
apps/api/app/core/security.py:123:        async with httpx.AsyncClient(timeout=5.0) as client:
apps/api/app/core/security.py:124:            response = await client.get(url)
apps/api/app/core/security.py:125:            response.raise_for_status()
apps/api/app/core/security.py:126:            _jwks_cache = response.json()
apps/api/app/core/security.py:127:            _jwks_fetched_at = time.monotonic()
apps/api/app/core/security.py:128:    except Exception:  # noqa: BLE001
apps/api/app/core/security.py:129:        if not _jwks_cache:
apps/api/app/core/security.py:130:            raise HTTPException(
apps/api/app/core/security.py:131:                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
apps/api/app/core/security.py:132:                detail="identity provider unavailable",
apps/api/app/core/security.py:133:            ) from None
apps/api/app/core/security.py:134:        # Stale keys beat no service; the next request retries.
apps/api/app/core/security.py:135:    return _jwks_cache
apps/api/app/core/security.py:136:
apps/api/app/core/security.py:137:
apps/api/app/core/security.py:138:async def _decode(token: str) -> dict[str, Any]:
apps/api/app/core/security.py:139:    """Verify signature, issuer, audience and expiry. All four."""
apps/api/app/core/security.py:140:    jwks = await _get_jwks()
apps/api/app/core/security.py:141:    try:
apps/api/app/core/security.py:142:        # cast: python-jose is untyped, so decode() is Any. The claims are
apps/api/app/core/security.py:143:        # validated by the options below, not by the type system.
apps/api/app/core/security.py:144:        decoded: dict[str, Any] = jwt.decode(
apps/api/app/core/security.py:145:            token,
apps/api/app/core/security.py:146:            jwks,
apps/api/app/core/security.py:147:            algorithms=["RS256"],
apps/api/app/core/security.py:148:            audience=settings.keycloak_audience,
apps/api/app/core/security.py:149:            issuer=settings.keycloak_issuer,
apps/api/app/core/security.py:150:            options={
apps/api/app/core/security.py:151:                "verify_signature": True,
apps/api/app/core/security.py:152:                "verify_aud": True,
apps/api/app/core/security.py:153:                "verify_iss": True,
apps/api/app/core/security.py:154:                "verify_exp": True,
apps/api/app/core/security.py:155:            },
apps/api/app/core/security.py:156:        )
apps/api/app/core/security.py:157:        return decoded
apps/api/app/core/security.py:158:    except JWTError as exc:
apps/api/app/core/security.py:159:        raise HTTPException(
apps/api/app/core/security.py:160:            status_code=status.HTTP_401_UNAUTHORIZED,
apps/api/app/core/security.py:161:            detail="invalid token",
apps/api/app/core/security.py:162:            headers={"WWW-Authenticate": "Bearer"},
apps/api/app/core/security.py:163:        ) from exc
apps/api/app/core/security.py:164:
apps/api/app/core/security.py:165:
apps/api/app/core/security.py:166:# ---------------------------------------------------------------------------
apps/api/app/core/security.py:167:# Principal resolution
apps/api/app/core/security.py:168:# ---------------------------------------------------------------------------
apps/api/app/core/security.py:169:
apps/api/app/core/security.py:170:_PRINCIPAL_SQL = text(
apps/api/app/core/security.py:171:    """
apps/api/app/core/security.py:172:    SELECT u.id                AS user_id,
apps/api/app/core/security.py:173:           u.email             AS email,
apps/api/app/core/security.py:174:           u.display_name      AS display_name,
apps/api/app/core/security.py:175:           om.organization_id  AS organization_id,
apps/api/app/core/security.py:176:           COALESCE(array_agg(DISTINCT r.code)
apps/api/app/core/security.py:177:                    FILTER (WHERE r.code IS NOT NULL), '{}') AS roles,
apps/api/app/core/security.py:178:           COALESCE(array_agg(DISTINCT p.code)
apps/api/app/core/security.py:179:                    FILTER (WHERE p.code IS NOT NULL), '{}') AS permissions
apps/api/app/core/security.py:180:    FROM core.users u
apps/api/app/core/security.py:181:    JOIN core.organization_members om
apps/api/app/core/security.py:182:      ON om.user_id = u.id AND om.status = 'active'
apps/api/app/core/security.py:183:    LEFT JOIN core.member_roles mr   ON mr.member_id = om.id
apps/api/app/core/security.py:184:    LEFT JOIN core.roles r           ON r.id = mr.role_id
apps/api/app/core/security.py:185:    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
apps/api/app/core/security.py:186:    LEFT JOIN core.permissions p     ON p.id = rp.permission_id
apps/api/app/core/security.py:187:    WHERE u.keycloak_sub = :sub
apps/api/app/core/security.py:188:      AND u.status = 'active'
apps/api/app/core/security.py:189:      AND om.organization_id = :org_id
apps/api/app/core/security.py:190:    GROUP BY u.id, u.email, u.display_name, om.organization_id
apps/api/app/core/security.py:191:    """
apps/api/app/core/security.py:192:)
apps/api/app/core/security.py:193:
apps/api/app/core/security.py:194:
apps/api/app/core/security.py:195:async def get_verified_subject(
apps/api/app/core/security.py:196:    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
apps/api/app/core/security.py:197:) -> str:
apps/api/app/core/security.py:198:    """The token's subject, with no organization required.
apps/api/app/core/security.py:199:
apps/api/app/core/security.py:200:    🔴 THIS IS THE ONLY AUTHENTICATED ENTRY POINT THAT DOES NOT DEMAND A
apps/api/app/core/security.py:201:    TENANT, AND IT EXISTS FOR EXACTLY ONE ROUTE.
apps/api/app/core/security.py:202:
apps/api/app/core/security.py:203:    ``get_principal`` requires ``X-Organization-Id``, correctly -- picking
apps/api/app/core/security.py:204:    a default tenant for a user who belongs to several writes records into
apps/api/app/core/security.py:205:    whichever one happened to sort first. But every authenticated route
apps/api/app/core/security.py:206:    depends on it, so a browser that had just signed in held a valid token
apps/api/app/core/security.py:207:    and no way to discover a tenant to ask for. Authentication completed
apps/api/app/core/security.py:208:    and the application was still unusable. ``GET /api/me`` closes that,
apps/api/app/core/security.py:209:    and needs identity before tenancy to do it.
apps/api/app/core/security.py:210:
apps/api/app/core/security.py:211:    The verification is identical to ``get_principal``'s -- the same
apps/api/app/core/security.py:212:    ``_decode``, so signature, issuer, audience and expiry are all checked.
apps/api/app/core/security.py:213:    What is deliberately absent is the ORGANIZATION step, and nothing else.
apps/api/app/core/security.py:214:
apps/api/app/core/security.py:215:    It returns a bare ``str`` rather than a ``Principal`` on purpose: a
apps/api/app/core/security.py:216:    Principal without an organization would be a Principal that could be
apps/api/app/core/security.py:217:    passed to something expecting one, and ``Principal.context`` would then
apps/api/app/core/security.py:218:    be constructed from a tenant nobody chose. There is no such object, so
apps/api/app/core/security.py:219:    there is no such mistake to make.
apps/api/app/core/security.py:220:    """
apps/api/app/core/security.py:221:    if credentials is None:
apps/api/app/core/security.py:222:        raise HTTPException(
apps/api/app/core/security.py:223:            status_code=status.HTTP_401_UNAUTHORIZED,
apps/api/app/core/security.py:224:            detail="missing bearer token",
apps/api/app/core/security.py:225:            headers={"WWW-Authenticate": "Bearer"},
apps/api/app/core/security.py:226:        )
apps/api/app/core/security.py:227:    claims = await _decode(credentials.credentials)
apps/api/app/core/security.py:228:    sub = claims.get("sub")
apps/api/app/core/security.py:229:    if not isinstance(sub, str) or not sub:
apps/api/app/core/security.py:230:        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")
apps/api/app/core/security.py:231:    return sub
apps/api/app/core/security.py:232:
apps/api/app/core/security.py:233:
apps/api/app/core/security.py:234:async def get_principal(
apps/api/app/core/security.py:235:    request: Request,
apps/api/app/core/security.py:236:    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
apps/api/app/core/security.py:237:) -> Principal:
apps/api/app/core/security.py:238:    """Resolve the caller, or refuse.
apps/api/app/core/security.py:239:
apps/api/app/core/security.py:240:    Membership and permissions are read from the database rather than
apps/api/app/core/security.py:241:    trusted from the token's claims. A JWT is a statement about identity;
apps/api/app/core/security.py:242:    it is not a current statement about authorization. Revoking a
apps/api/app/core/security.py:243:    membership must take effect immediately, not when the access token
apps/api/app/core/security.py:244:    happens to expire.
apps/api/app/core/security.py:245:    """
apps/api/app/core/security.py:246:    if credentials is None:
apps/api/app/core/security.py:247:        raise HTTPException(
apps/api/app/core/security.py:248:            status_code=status.HTTP_401_UNAUTHORIZED,
apps/api/app/core/security.py:249:            detail="missing bearer token",
apps/api/app/core/security.py:250:            headers={"WWW-Authenticate": "Bearer"},
apps/api/app/core/security.py:251:        )
apps/api/app/core/security.py:252:
apps/api/app/core/security.py:253:    claims = await _decode(credentials.credentials)
apps/api/app/core/security.py:254:
apps/api/app/core/security.py:255:    sub = claims.get("sub")
apps/api/app/core/security.py:256:    if not sub:
apps/api/app/core/security.py:257:        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")
apps/api/app/core/security.py:258:
apps/api/app/core/security.py:259:    # Organization selection. A user may belong to several; the active one
apps/api/app/core/security.py:260:    # comes from a header, but it is a *request* to use that organization,
apps/api/app/core/security.py:261:    # validated against real membership below -- never taken on trust.
apps/api/app/core/security.py:262:    requested_org = request.headers.get("X-Organization-Id")
apps/api/app/core/security.py:263:    if not requested_org:
apps/api/app/core/security.py:264:        raise HTTPException(
apps/api/app/core/security.py:265:            status_code=status.HTTP_400_BAD_REQUEST,
apps/api/app/core/security.py:266:            detail="X-Organization-Id header is required",
apps/api/app/core/security.py:267:        )
apps/api/app/core/security.py:268:    try:
apps/api/app/core/security.py:269:        org_id = uuid.UUID(requested_org)
apps/api/app/core/security.py:270:    except ValueError:
apps/api/app/core/security.py:271:        raise HTTPException(
apps/api/app/core/security.py:272:            status_code=status.HTTP_400_BAD_REQUEST,
apps/api/app/core/security.py:273:            detail="X-Organization-Id is not a valid UUID",
apps/api/app/core/security.py:274:        ) from None
apps/api/app/core/security.py:275:
apps/api/app/core/security.py:276:    # Resolving the principal is itself a context-free read -- we cannot
apps/api/app/core/security.py:277:    # set the RLS GUCs until we know who the caller is. It is confined to
apps/api/app/core/security.py:278:    # core.users / core.organization_members and returns nothing from any
apps/api/app/core/security.py:279:    # project-scoped table, which is why this is a safe exception to the
apps/api/app/core/security.py:280:    # session_scope() rule.
apps/api/app/core/security.py:281:    from app.core.db import unscoped_session_scope
apps/api/app/core/security.py:282:
apps/api/app/core/security.py:283:    with unscoped_session_scope() as session:
apps/api/app/core/security.py:284:        row = (
apps/api/app/core/security.py:285:            session.execute(_PRINCIPAL_SQL, {"sub": sub, "org_id": org_id}).mappings().one_or_none()
apps/api/app/core/security.py:286:        )
apps/api/app/core/security.py:287:
apps/api/app/core/security.py:288:    if row is None:
apps/api/app/core/security.py:289:        # Not a member of the requested organization -- or no such
apps/api/app/core/security.py:290:        # organization. Deliberately the same answer for both.
apps/api/app/core/security.py:291:        raise PermissionDenied("not a member of the requested organization")
apps/api/app/core/security.py:292:
apps/api/app/core/security.py:293:    return Principal(
apps/api/app/core/security.py:294:        user_id=row["user_id"],
apps/api/app/core/security.py:295:        organization_id=row["organization_id"],
apps/api/app/core/security.py:296:        keycloak_sub=sub,
apps/api/app/core/security.py:297:        email=row["email"],
apps/api/app/core/security.py:298:        display_name=row["display_name"],
apps/api/app/core/security.py:299:        roles=frozenset(row["roles"]),
apps/api/app/core/security.py:300:        permissions=frozenset(row["permissions"]),
apps/api/app/core/security.py:301:        session_id=claims.get("sid"),
apps/api/app/core/security.py:302:    )
apps/api/app/core/security.py:303:
apps/api/app/core/security.py:304:
apps/api/app/core/security.py:305:def get_db(principal: Principal = Depends(get_principal)) -> Iterator[Session]:
apps/api/app/core/security.py:306:    """Yield a session with the caller's RLS context applied.
apps/api/app/core/security.py:307:
apps/api/app/core/security.py:308:    This is the only supported route to the database in request handling.
apps/api/app/core/security.py:309:    Because it depends on ``get_principal``, there is no way to obtain a
apps/api/app/core/security.py:310:    session without first having been authenticated and having proven
apps/api/app/core/security.py:311:    organization membership.
apps/api/app/core/security.py:312:    """
apps/api/app/core/security.py:313:    with session_scope(principal.context) as session:
apps/api/app/core/security.py:314:        yield session
apps/api/app/core/security.py:315:
apps/api/app/core/security.py:316:
apps/api/app/core/security.py:317:# ---------------------------------------------------------------------------
apps/api/app/core/security.py:318:# Authorization dependencies
apps/api/app/core/security.py:319:# ---------------------------------------------------------------------------
apps/api/app/core/security.py:320:
apps/api/app/core/security.py:321:
apps/api/app/core/security.py:322:def require_permission(*permissions: str, require_all: bool = False) -> Callable[..., Principal]:
apps/api/app/core/security.py:323:    """Dependency factory: assert the caller holds the permission(s).
apps/api/app/core/security.py:324:
apps/api/app/core/security.py:325:    Args:
apps/api/app/core/security.py:326:        permissions: permission codes, e.g. ``"formula.approve_lab"``.
apps/api/app/core/security.py:327:        require_all: if True the caller needs every one; default is any.
apps/api/app/core/security.py:328:    """
apps/api/app/core/security.py:329:
apps/api/app/core/security.py:330:    def _check(principal: Principal = Depends(get_principal)) -> Principal:
apps/api/app/core/security.py:331:        held = principal.permissions
apps/api/app/core/security.py:332:        ok = (
apps/api/app/core/security.py:333:            all(p in held for p in permissions)
apps/api/app/core/security.py:334:            if require_all
apps/api/app/core/security.py:335:            else any(p in held for p in permissions)
apps/api/app/core/security.py:336:        )
apps/api/app/core/security.py:337:        if not ok:
apps/api/app/core/security.py:338:            raise PermissionDenied()
apps/api/app/core/security.py:339:        return principal
apps/api/app/core/security.py:340:
apps/api/app/core/security.py:341:    return _check
apps/api/app/core/security.py:342:
apps/api/app/core/security.py:343:
apps/api/app/core/security.py:344:def require_project_member(
apps/api/app/core/security.py:345:    project_id_param: str = "project_id",
apps/api/app/core/security.py:346:) -> Callable[..., Principal]:
apps/api/app/core/security.py:347:    """Dependency factory: assert membership of the project in the path.
apps/api/app/core/security.py:348:
apps/api/app/core/security.py:349:    Separate from :func:`require_permission` on purpose. Permission asks
apps/api/app/core/security.py:350:    "may this person ever do this?"; scope asks "may they do it *here*?"
apps/api/app/core/security.py:351:    Both must pass, and RLS independently enforces the same answer at the
apps/api/app/core/security.py:352:    database layer, so a mistake in either one is caught by the other.
apps/api/app/core/security.py:353:    """
apps/api/app/core/security.py:354:
apps/api/app/core/security.py:355:    def _check(
apps/api/app/core/security.py:356:        request: Request,
apps/api/app/core/security.py:357:        principal: Principal = Depends(get_principal),
apps/api/app/core/security.py:358:        session: Session = Depends(get_db),
apps/api/app/core/security.py:359:    ) -> Principal:
apps/api/app/core/security.py:360:        raw = request.path_params.get(project_id_param)
apps/api/app/core/security.py:361:        if raw is None:
apps/api/app/core/security.py:362:            raise HTTPException(
apps/api/app/core/security.py:363:                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
apps/api/app/core/security.py:364:                detail=f"route has no path parameter '{project_id_param}'",
apps/api/app/core/security.py:365:            )
apps/api/app/core/security.py:366:        try:
apps/api/app/core/security.py:367:            project_id = uuid.UUID(str(raw))
apps/api/app/core/security.py:368:        except ValueError:
apps/api/app/core/security.py:369:            raise PermissionDenied() from None
apps/api/app/core/security.py:370:
apps/api/app/core/security.py:371:        # core.is_project_member() is the single definition of membership,
apps/api/app/core/security.py:372:        # shared with every RLS policy. Asking the database rather than
apps/api/app/core/security.py:373:        # reimplementing the predicate is what stops the rule drifting
apps/api/app/core/security.py:374:        # between the API and the policies.
apps/api/app/core/security.py:375:        is_member = session.execute(
apps/api/app/core/security.py:376:            text("SELECT core.is_project_member(:pid)"), {"pid": project_id}
apps/api/app/core/security.py:377:        ).scalar_one()
apps/api/app/core/security.py:378:
apps/api/app/core/security.py:379:        if not is_member:
apps/api/app/core/security.py:380:            raise PermissionDenied()
apps/api/app/core/security.py:381:        return principal
apps/api/app/core/security.py:382:
apps/api/app/core/security.py:383:    return _check
apps/api/app/core/config.py:1:"""Application settings.
apps/api/app/core/config.py:3:Every value is read from the environment. Nothing sensitive has a default
apps/api/app/core/config.py:4:-- a missing database password should stop the process at startup, not
apps/api/app/core/config.py:5:silently connect somewhere unintended.
apps/api/app/core/config.py:7:Secrets reach the environment through SOPS + age (SECURITY.md §12), never
apps/api/app/core/config.py:8:from a committed file. Note for anyone writing a secrets file on this
apps/api/app/core/config.py:9:host: PowerShell pipelines add a UTF-16 BOM, which makes the first key
apps/api/app/core/config.py:10:unparseable in a way that looks like a wrong password. Write UTF-8
apps/api/app/core/config.py:11:explicitly.
apps/api/app/core/config.py:12:"""
apps/api/app/core/config.py:14:from __future__ import annotations
apps/api/app/core/config.py:16:from functools import lru_cache
apps/api/app/core/config.py:17:from typing import Literal
apps/api/app/core/config.py:19:from pydantic import Field, field_validator
apps/api/app/core/config.py:20:from pydantic_settings import BaseSettings, SettingsConfigDict
apps/api/app/core/config.py:22:__all__ = ["Settings", "get_settings", "settings"]
apps/api/app/core/config.py:25:class Settings(BaseSettings):
apps/api/app/core/config.py:26:    model_config = SettingsConfigDict(
apps/api/app/core/config.py:27:        env_file=".env",
apps/api/app/core/config.py:28:        env_file_encoding="utf-8",
apps/api/app/core/config.py:29:        extra="ignore",
apps/api/app/core/config.py:30:        case_sensitive=False,
apps/api/app/core/config.py:31:    )
apps/api/app/core/config.py:33:    # --- Identity -------------------------------------------------------
apps/api/app/core/config.py:34:    app_name: str = "EvercoatITWRD APP"
apps/api/app/core/config.py:35:    app_slug: str = "evercoat-itw-rd"
apps/api/app/core/config.py:36:    app_env: Literal["development", "staging", "production"] = "development"
apps/api/app/core/config.py:38:    # --- Database -------------------------------------------------------
apps/api/app/core/config.py:39:    # No default. The app must never guess a connection string.
apps/api/app/core/config.py:40:    database_url: str = Field(..., description="SQLAlchemy URL for the runtime app role")
apps/api/app/core/config.py:41:    db_pool_size: int = 10
apps/api/app/core/config.py:42:    db_max_overflow: int = 5
apps/api/app/core/config.py:43:    db_echo: bool = False
apps/api/app/core/config.py:45:    # --- Keycloak -------------------------------------------------------
apps/api/app/core/config.py:46:    keycloak_issuer: str = Field(..., description="Realm issuer URL")
apps/api/app/core/config.py:47:    keycloak_audience: str = Field(default="evercoat-api")
apps/api/app/core/config.py:48:    # JWKS is cached; this bounds how long a revoked signing key stays
apps/api/app/core/config.py:49:    # trusted after a realm key rotation.
apps/api/app/core/config.py:50:    jwks_cache_seconds: int = 300
apps/api/app/core/config.py:52:    # --- Cache / worker -------------------------------------------------
apps/api/app/core/config.py:53:    valkey_url: str = "redis://valkey:6379/0"
apps/api/app/core/config.py:55:    # --- Object storage -------------------------------------------------
apps/api/app/core/config.py:56:    garage_endpoint: str = "http://garage:3900"
apps/api/app/core/config.py:57:    garage_bucket: str = "evercoat-documents"
apps/api/app/core/config.py:58:    garage_access_key: str | None = None
apps/api/app/core/config.py:59:    garage_secret_key: str | None = None
apps/api/app/core/config.py:60:    # Short by design. A signed URL outlives access revocation (Codex F38),
apps/api/app/core/config.py:61:    # so the window is kept small and sensitive formulation documents go
apps/api/app/core/config.py:62:    # through an authorization-checking proxy instead.
apps/api/app/core/config.py:63:    signed_url_ttl_seconds: int = 120
apps/api/app/core/config.py:65:    # --- AI (Slice 7 onward) --------------------------------------------
apps/api/app/core/config.py:66:    # Local runtime only. The zero-cost rule forbids an essential paid AI
apps/api/app/core/config.py:67:    # API, and proprietary formulations must not leave the organization's
apps/api/app/core/config.py:68:    # infrastructure -- that is a security property first, cost second.
apps/api/app/core/config.py:69:    ollama_base_url: str = "http://ollama:11434"
apps/api/app/core/config.py:70:    ollama_model: str | None = None  # chosen from measured memory headroom
apps/api/app/core/config.py:72:    # --- Observability --------------------------------------------------
apps/api/app/core/config.py:73:    log_format: Literal["json", "console"] = "json"
apps/api/app/core/config.py:74:    log_level: str = "INFO"
apps/api/app/core/config.py:75:    metrics_enabled: bool = True
apps/api/app/core/config.py:77:    # --- Security -------------------------------------------------------
apps/api/app/core/config.py:78:    cors_allowed_origins: list[str] = Field(default_factory=list)
apps/api/app/core/config.py:80:    @field_validator("database_url")
apps/api/app/core/config.py:81:    @classmethod
apps/api/app/core/config.py:82:    def _reject_superuser(cls, v: str) -> str:
apps/api/app/core/config.py:83:        """Refuse to start as a database superuser.
apps/api/app/core/config.py:85:        Superuser bypasses Row Level Security. Running the application as
apps/api/app/core/config.py:86:        one hides exactly the defects RLS exists to catch, and they would
apps/api/app/core/config.py:87:        only surface in production (ADR-017). This is a cheap guard
apps/api/app/core/config.py:88:        against a mistake that is expensive and silent.
apps/api/app/core/config.py:89:        """
apps/api/app/core/config.py:90:        lowered = v.lower()
apps/api/app/core/config.py:91:        for forbidden in ("://postgres:", "://postgres@", "user=postgres"):
apps/api/app/core/config.py:92:            if forbidden in lowered:
apps/api/app/core/config.py:93:                raise ValueError(
apps/api/app/core/config.py:94:                    "the application must not connect as a database superuser; "
apps/api/app/core/config.py:95:                    "use the evercoat_app role, which is subject to FORCE RLS"
apps/api/app/core/config.py:96:                )
apps/api/app/core/config.py:97:        return v
apps/api/app/core/config.py:99:    @field_validator("cors_allowed_origins")
apps/api/app/core/config.py:100:    @classmethod
apps/api/app/core/config.py:101:    def _no_wildcard_in_prod(cls, v: list[str], info) -> list[str]:  # type: ignore[no-untyped-def]
apps/api/app/core/config.py:102:        if "*" in v and info.data.get("app_env") == "production":
apps/api/app/core/config.py:103:            raise ValueError("wildcard CORS origin is not permitted in production")
apps/api/app/core/config.py:104:        return v
apps/api/app/core/config.py:106:    @property
apps/api/app/core/config.py:107:    def is_production(self) -> bool:
apps/api/app/core/config.py:108:        return self.app_env == "production"
apps/api/app/core/config.py:111:@lru_cache(maxsize=1)
apps/api/app/core/config.py:112:def get_settings() -> Settings:
apps/api/app/core/config.py:113:    return Settings()  # type: ignore[call-arg]
apps/api/app/core/config.py:116:settings = get_settings()
apps/api/app/core/logging.py:1:"""Structured JSON logging with typed channels.
apps/api/app/core/logging.py:2:
apps/api/app/core/logging.py:3:Reused in shape from Solar's ``logging_config/structured_logger.py``
apps/api/app/core/logging.py:4:(REUSE.md R5), with the channels remapped to this domain. Typed channels
apps/api/app/core/logging.py:5:matter because "find every authorization failure last week" and "find
apps/api/app/core/logging.py:6:every formula approval last week" are different questions, and grepping
apps/api/app/core/logging.py:7:one undifferentiated stream answers neither well.
apps/api/app/core/logging.py:8:
apps/api/app/core/logging.py:9:**What must never appear in a log line:** formula compositions, component
apps/api/app/core/logging.py:10:percentages, secrets, tokens, or full request bodies from formulation
apps/api/app/core/logging.py:11:endpoints (SECURITY.md §11). Log identifiers and outcomes, not payloads.
apps/api/app/core/logging.py:12:A log aggregator is not access-controlled the way the database is, so a
apps/api/app/core/logging.py:13:formula that leaks into Loki has left the protected boundary.
apps/api/app/core/logging.py:14:"""
apps/api/app/core/logging.py:15:
apps/api/app/core/logging.py:16:from __future__ import annotations
apps/api/app/core/logging.py:17:
apps/api/app/core/logging.py:18:import logging
apps/api/app/core/logging.py:19:import sys
apps/api/app/core/logging.py:20:from typing import Any, Literal
apps/api/app/core/logging.py:21:
apps/api/app/core/logging.py:22:import structlog
apps/api/app/core/logging.py:23:
apps/api/app/core/logging.py:24:from app.core.config import settings
apps/api/app/core/logging.py:25:
apps/api/app/core/logging.py:26:__all__ = [
apps/api/app/core/logging.py:27:    "configure_logging",
apps/api/app/core/logging.py:28:    "log_ai",
apps/api/app/core/logging.py:29:    "log_audit",
apps/api/app/core/logging.py:30:    "log_formulation",
apps/api/app/core/logging.py:31:    "log_laboratory",
apps/api/app/core/logging.py:32:    "log_queue",
apps/api/app/core/logging.py:33:    "log_security",
apps/api/app/core/logging.py:34:    "log_testing",
apps/api/app/core/logging.py:35:]
apps/api/app/core/logging.py:36:
apps/api/app/core/logging.py:37:Channel = Literal[
apps/api/app/core/logging.py:38:    "app",
apps/api/app/core/logging.py:39:    "audit",
apps/api/app/core/logging.py:40:    "security",
apps/api/app/core/logging.py:41:    "formulation",
apps/api/app/core/logging.py:42:    "laboratory",
apps/api/app/core/logging.py:43:    "testing",
apps/api/app/core/logging.py:44:    "ai",
apps/api/app/core/logging.py:45:    "queue",
apps/api/app/core/logging.py:46:    "error",
apps/api/app/core/logging.py:47:]
apps/api/app/core/logging.py:48:
apps/api/app/core/logging.py:49:# Keys that must never be emitted, whatever a caller passes.
apps/api/app/core/logging.py:50:_REDACT = frozenset(
apps/api/app/core/logging.py:51:    {
apps/api/app/core/logging.py:52:        "password",
apps/api/app/core/logging.py:53:        "secret",
apps/api/app/core/logging.py:54:        "token",
apps/api/app/core/logging.py:55:        "access_token",
apps/api/app/core/logging.py:56:        "refresh_token",
apps/api/app/core/logging.py:57:        "authorization",
apps/api/app/core/logging.py:58:        "api_key",
apps/api/app/core/logging.py:59:        "client_secret",
apps/api/app/core/logging.py:60:        "private_key",
apps/api/app/core/logging.py:61:        "components",
apps/api/app/core/logging.py:62:        "composition",
apps/api/app/core/logging.py:63:        "weight_percent",
apps/api/app/core/logging.py:64:        "formula_components",
apps/api/app/core/logging.py:65:    }
apps/api/app/core/logging.py:66:)
apps/api/app/core/logging.py:67:
apps/api/app/core/logging.py:68:
apps/api/app/core/logging.py:69:def _redact(_logger: Any, _method: str, event: dict[str, Any]) -> dict[str, Any]:
apps/api/app/core/logging.py:70:    """Drop forbidden keys rather than masking them.
apps/api/app/core/logging.py:71:
apps/api/app/core/logging.py:72:    Masking still confirms the field was present and hints at its length.
apps/api/app/core/logging.py:73:    For a formulation percentage that is already a meaningful leak, so the
apps/api/app/core/logging.py:74:    key is removed entirely and replaced with a marker.
apps/api/app/core/logging.py:75:    """
apps/api/app/core/logging.py:76:    for key in list(event):
apps/api/app/core/logging.py:77:        if key.lower() in _REDACT:
apps/api/app/core/logging.py:78:            event[key] = "<redacted>"
apps/api/app/core/logging.py:79:    return event
apps/api/app/core/logging.py:80:
apps/api/app/core/logging.py:81:
apps/api/app/core/logging.py:82:def configure_logging() -> None:
apps/api/app/core/logging.py:83:    # structlog's NATIVE processors, not the .stdlib ones.
apps/api/app/core/logging.py:84:    #
apps/api/app/core/logging.py:85:    # `structlog.stdlib.add_logger_name` reads `logger.name`, which only
apps/api/app/core/logging.py:86:    # exists on a stdlib logger. Paired with PrintLoggerFactory below it
apps/api/app/core/logging.py:87:    # raises AttributeError on the very first log line — which meant the
apps/api/app/core/logging.py:88:    # application aborted during startup, before binding a port, with the
apps/api/app/core/logging.py:89:    # failure buried in a structlog traceback rather than anything that
apps/api/app/core/logging.py:90:    # looked like a logging problem.
apps/api/app/core/logging.py:91:    #
apps/api/app/core/logging.py:92:    # PrintLoggerFactory is kept deliberately: it needs no stdlib logging
apps/api/app/core/logging.py:93:    # configuration, writes straight to stdout for the container runtime
apps/api/app/core/logging.py:94:    # to collect, and is faster. So the processors match the factory
apps/api/app/core/logging.py:95:    # instead of the factory matching the processors.
apps/api/app/core/logging.py:96:    processors: list[Any] = [
apps/api/app/core/logging.py:97:        structlog.contextvars.merge_contextvars,
apps/api/app/core/logging.py:98:        structlog.processors.add_log_level,
apps/api/app/core/logging.py:99:        structlog.processors.TimeStamper(fmt="iso", utc=True),
apps/api/app/core/logging.py:100:        _redact,
apps/api/app/core/logging.py:101:        structlog.processors.StackInfoRenderer(),
apps/api/app/core/logging.py:102:        structlog.processors.format_exc_info,
apps/api/app/core/logging.py:103:    ]
apps/api/app/core/logging.py:104:    processors.append(
apps/api/app/core/logging.py:105:        structlog.processors.JSONRenderer()
apps/api/app/core/logging.py:106:        if settings.log_format == "json"
apps/api/app/core/logging.py:107:        else structlog.dev.ConsoleRenderer(colors=True)
apps/api/app/core/logging.py:108:    )
apps/api/app/core/logging.py:109:
apps/api/app/core/logging.py:110:    structlog.configure(
apps/api/app/core/logging.py:111:        processors=processors,
apps/api/app/core/logging.py:112:        wrapper_class=structlog.make_filtering_bound_logger(
apps/api/app/core/logging.py:113:            logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
apps/api/app/core/logging.py:114:        ),
apps/api/app/core/logging.py:115:        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
apps/api/app/core/logging.py:116:        cache_logger_on_first_use=True,
apps/api/app/core/logging.py:117:    )
apps/api/app/core/logging.py:118:
apps/api/app/core/logging.py:119:
apps/api/app/core/logging.py:120:def _emit(channel: Channel, event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:121:    # channel is bound as a FIELD, not as a logger name. PrintLogger
apps/api/app/core/logging.py:122:    # has no name, so a name would simply vanish -- and a typed channel
apps/api/app/core/logging.py:123:    # that silently disappears is worse than none, because the queries
apps/api/app/core/logging.py:124:    # written against it return empty rather than failing.
apps/api/app/core/logging.py:125:    structlog.get_logger().info(event, channel=channel, **kwargs)
apps/api/app/core/logging.py:126:
apps/api/app/core/logging.py:127:
apps/api/app/core/logging.py:128:def log_audit(action: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:129:    """User actions on controlled records.
apps/api/app/core/logging.py:130:
apps/api/app/core/logging.py:131:    This is the *operational* log of an action. It is not the audit trail
apps/api/app/core/logging.py:132:    -- ``audit.events`` is, and it is hash-chained and append-only. A log
apps/api/app/core/logging.py:133:    line can be lost, rotated or tampered with; the chain cannot, silently.
apps/api/app/core/logging.py:134:    Never treat this as evidence.
apps/api/app/core/logging.py:135:    """
apps/api/app/core/logging.py:136:    _emit("audit", action, **kwargs)
apps/api/app/core/logging.py:137:
apps/api/app/core/logging.py:138:
apps/api/app/core/logging.py:139:def log_security(event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:140:    """Auth failures, tenant violations, permission denials."""
apps/api/app/core/logging.py:141:    _emit("security", event, **kwargs)
apps/api/app/core/logging.py:142:
apps/api/app/core/logging.py:143:
apps/api/app/core/logging.py:144:def log_formulation(event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:145:    """Formula lifecycle. Identifiers and outcomes only -- never composition."""
apps/api/app/core/logging.py:146:    _emit("formulation", event, **kwargs)
apps/api/app/core/logging.py:147:
apps/api/app/core/logging.py:148:
apps/api/app/core/logging.py:149:def log_laboratory(event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:150:    _emit("laboratory", event, **kwargs)
apps/api/app/core/logging.py:151:
apps/api/app/core/logging.py:152:
apps/api/app/core/logging.py:153:def log_testing(event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:154:    _emit("testing", event, **kwargs)
apps/api/app/core/logging.py:155:
apps/api/app/core/logging.py:156:
apps/api/app/core/logging.py:157:def log_ai(event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:158:    """MSD runs. Record which records were retrieved, not their contents."""
apps/api/app/core/logging.py:159:    _emit("ai", event, **kwargs)
apps/api/app/core/logging.py:160:
apps/api/app/core/logging.py:161:
apps/api/app/core/logging.py:162:def log_queue(event: str, **kwargs: Any) -> None:
apps/api/app/core/logging.py:163:    _emit("queue", event, **kwargs)
apps/api/app/main.py:1:"""EvercoatITWRD APP — FastAPI entrypoint.
apps/api/app/main.py:2:
apps/api/app/main.py:3:Observability lands in Slice 1 rather than Slice 20 (Codex F43): the
apps/api/app/main.py:4:slice gate requires every feature to be exercised on a *deployed*
apps/api/app/main.py:5:instance from Slice 1 onward, and you cannot diagnose a deployed instance
apps/api/app/main.py:6:that has no health endpoint, no structured logs and no metrics.
apps/api/app/main.py:7:"""
apps/api/app/main.py:8:
apps/api/app/main.py:9:from __future__ import annotations
apps/api/app/main.py:10:
apps/api/app/main.py:11:import time
apps/api/app/main.py:12:import uuid
apps/api/app/main.py:13:from collections.abc import Awaitable, Callable
apps/api/app/main.py:14:from contextlib import asynccontextmanager
apps/api/app/main.py:15:
apps/api/app/main.py:16:import structlog
apps/api/app/main.py:17:from fastapi import FastAPI, Request, Response
apps/api/app/main.py:18:from fastapi.middleware.cors import CORSMiddleware
apps/api/app/main.py:19:from fastapi.responses import JSONResponse
apps/api/app/main.py:20:from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
apps/api/app/main.py:21:
apps/api/app/main.py:22:from app.api.admin import router as admin_router
apps/api/app/main.py:23:from app.api.admin_reference_data import router as admin_reference_data_router
apps/api/app/main.py:24:from app.api.admin_stage_gates import router as admin_stage_gates_router
apps/api/app/main.py:25:from app.api.failures import approvals_router
apps/api/app/main.py:26:from app.api.failures import router as failures_router
apps/api/app/main.py:27:from app.api.formulations import router as formulations_router
apps/api/app/main.py:28:from app.api.health import router as health_router
apps/api/app/main.py:29:from app.api.laboratory import router as laboratory_router
apps/api/app/main.py:30:from app.api.materials import router as materials_router
apps/api/app/main.py:31:from app.api.materials import suppliers_router
apps/api/app/main.py:32:from app.api.me import router as me_router
apps/api/app/main.py:33:from app.api.messaging import router as messaging_router
apps/api/app/main.py:34:from app.api.opportunities import router as opportunities_router
apps/api/app/main.py:35:from app.api.projects import router as projects_router
apps/api/app/main.py:36:from app.api.tasks import router as tasks_router
apps/api/app/main.py:37:from app.api.testing import router as testing_router
apps/api/app/main.py:38:from app.core.config import settings
apps/api/app/main.py:39:from app.core.logging import configure_logging
apps/api/app/main.py:40:
apps/api/app/main.py:41:__all__ = ["app", "create_app"]
apps/api/app/main.py:42:
apps/api/app/main.py:43:configure_logging()
apps/api/app/main.py:44:log = structlog.get_logger(__name__)
apps/api/app/main.py:45:
apps/api/app/main.py:46:REQUESTS = Counter(
apps/api/app/main.py:47:    "evercoat_http_requests_total",
apps/api/app/main.py:48:    "HTTP requests",
apps/api/app/main.py:49:    ["method", "path", "status"],
apps/api/app/main.py:50:)
apps/api/app/main.py:51:LATENCY = Histogram(
apps/api/app/main.py:52:    "evercoat_http_request_seconds",
apps/api/app/main.py:53:    "HTTP request latency",
apps/api/app/main.py:54:    ["method", "path"],
apps/api/app/main.py:55:)
apps/api/app/main.py:56:
apps/api/app/main.py:57:
apps/api/app/main.py:58:@asynccontextmanager
apps/api/app/main.py:59:async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
apps/api/app/main.py:60:    log.info(
apps/api/app/main.py:61:        "startup",
apps/api/app/main.py:62:        app=settings.app_name,
apps/api/app/main.py:63:        env=settings.app_env,
apps/api/app/main.py:64:        version=app.version,
apps/api/app/main.py:65:    )
apps/api/app/main.py:66:    yield
apps/api/app/main.py:67:    log.info("shutdown", app=settings.app_name)
apps/api/app/main.py:68:
apps/api/app/main.py:69:
apps/api/app/main.py:70:def create_app() -> FastAPI:
apps/api/app/main.py:71:    application = FastAPI(
apps/api/app/main.py:72:        title=settings.app_name,
apps/api/app/main.py:73:        version="0.1.0",
apps/api/app/main.py:74:        description=(
apps/api/app/main.py:75:            "Integrated R&D, Smart Formulation, Laboratory Testing, "
apps/api/app/main.py:76:            "Product Modeling and Product Development Intelligence Platform"
apps/api/app/main.py:77:        ),
apps/api/app/main.py:78:        lifespan=lifespan,
apps/api/app/main.py:79:        # No interactive docs in production: the schema enumerates every
apps/api/app/main.py:80:        # controlled endpoint and is free reconnaissance.
apps/api/app/main.py:81:        docs_url=None if settings.is_production else "/docs",
apps/api/app/main.py:82:        redoc_url=None,
apps/api/app/main.py:83:        openapi_url=None if settings.is_production else "/openapi.json",
apps/api/app/main.py:84:    )
apps/api/app/main.py:85:
apps/api/app/main.py:86:    application.add_middleware(
apps/api/app/main.py:87:        CORSMiddleware,
apps/api/app/main.py:88:        allow_origins=settings.cors_allowed_origins,
apps/api/app/main.py:89:        allow_credentials=True,
apps/api/app/main.py:90:        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
apps/api/app/main.py:91:        allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-CSRF-Token"],
apps/api/app/main.py:92:    )
apps/api/app/main.py:93:
apps/api/app/main.py:94:    @application.middleware("http")
apps/api/app/main.py:95:    async def observe(
apps/api/app/main.py:96:        request: Request, call_next: Callable[[Request], Awaitable[Response]]
apps/api/app/main.py:97:    ) -> Response:
apps/api/app/main.py:98:        """Correlation id, structured access log, metrics.
apps/api/app/main.py:99:
apps/api/app/main.py:100:        The correlation id is echoed to the client and bound to every log
apps/api/app/main.py:101:        line for the request, so an incident can be reconstructed from the
apps/api/app/main.py:102:        audit trail plus traces (SECURITY.md §16).
apps/api/app/main.py:103:        """
apps/api/app/main.py:104:        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
apps/api/app/main.py:105:        structlog.contextvars.clear_contextvars()
apps/api/app/main.py:106:        structlog.contextvars.bind_contextvars(
apps/api/app/main.py:107:            correlation_id=correlation_id,
apps/api/app/main.py:108:            method=request.method,
apps/api/app/main.py:109:            path=request.url.path,
apps/api/app/main.py:110:        )
apps/api/app/main.py:111:
apps/api/app/main.py:112:        # Route template, not the concrete path: labelling metrics with
apps/api/app/main.py:113:        # /projects/<uuid> would create unbounded cardinality and take
apps/api/app/main.py:114:        # Prometheus down.
apps/api/app/main.py:115:        route = request.scope.get("route")
apps/api/app/main.py:116:        label_path = getattr(route, "path", request.url.path)
apps/api/app/main.py:117:
apps/api/app/main.py:118:        started = time.perf_counter()
apps/api/app/main.py:119:        try:
apps/api/app/main.py:120:            response = await call_next(request)
apps/api/app/main.py:121:        except Exception:
apps/api/app/main.py:122:            elapsed = time.perf_counter() - started
apps/api/app/main.py:123:            REQUESTS.labels(request.method, label_path, "500").inc()
apps/api/app/main.py:124:            LATENCY.labels(request.method, label_path).observe(elapsed)
apps/api/app/main.py:125:            # exc_info, but never the request body -- formulation payloads
apps/api/app/main.py:126:            # must not reach logs (SECURITY.md §11).
apps/api/app/main.py:127:            log.exception("request_failed", elapsed_ms=round(elapsed * 1000, 2))
apps/api/app/main.py:128:            return JSONResponse(
apps/api/app/main.py:129:                status_code=500,
apps/api/app/main.py:130:                content={"detail": "internal error", "correlation_id": correlation_id},
apps/api/app/main.py:131:                headers={"X-Correlation-Id": correlation_id},
apps/api/app/main.py:132:            )
apps/api/app/main.py:133:
apps/api/app/main.py:134:        elapsed = time.perf_counter() - started
apps/api/app/main.py:135:        REQUESTS.labels(request.method, label_path, str(response.status_code)).inc()
apps/api/app/main.py:136:        LATENCY.labels(request.method, label_path).observe(elapsed)
apps/api/app/main.py:137:        log.info(
apps/api/app/main.py:138:            "request",
apps/api/app/main.py:139:            status=response.status_code,
apps/api/app/main.py:140:            elapsed_ms=round(elapsed * 1000, 2),
apps/api/app/main.py:141:        )
apps/api/app/main.py:142:        response.headers["X-Correlation-Id"] = correlation_id
apps/api/app/main.py:143:        return response
apps/api/app/main.py:144:
apps/api/app/main.py:145:    @application.middleware("http")
apps/api/app/main.py:146:    async def security_headers(
apps/api/app/main.py:147:        request: Request, call_next: Callable[[Request], Awaitable[Response]]
apps/api/app/main.py:148:    ) -> Response:
apps/api/app/main.py:149:        response = await call_next(request)
apps/api/app/main.py:150:        response.headers["X-Content-Type-Options"] = "nosniff"
apps/api/app/main.py:151:        response.headers["X-Frame-Options"] = "DENY"
apps/api/app/main.py:152:        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
apps/api/app/main.py:153:        if settings.is_production:
apps/api/app/main.py:154:            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
apps/api/app/main.py:155:        return response
apps/api/app/main.py:156:
apps/api/app/main.py:157:    application.include_router(health_router, prefix="/health", tags=["health"])
apps/api/app/main.py:158:    # Administration section 1 -- the write path for users, roles and
apps/api/app/main.py:159:    # permissions. Live from Slice 1 (ADR-021): a configuration value
apps/api/app/main.py:160:    # with no screen is a value nobody can write.
apps/api/app/main.py:161:    application.include_router(admin_router, prefix="/api/admin")
apps/api/app/main.py:162:    # Administration section 2 -- stage-gate configuration. Same prefix,
apps/api/app/main.py:163:    # separate module: the pipeline reads stage_definitions on every
apps/api/app/main.py:164:    # transition, so ADR-021 requires the screen that writes them to ship
apps/api/app/main.py:165:    # in the same slice as the code that reads them.
apps/api/app/main.py:166:    application.include_router(admin_stage_gates_router, prefix="/api/admin")
apps/api/app/main.py:167:    # Administration section 3 -- units and product families. Slice 3's
apps/api/app/main.py:168:    # own Administration section: migration 015 creates the tables and
apps/api/app/main.py:169:    # this is their write path, so they do not join the list of tables
apps/api/app/main.py:170:    # nothing can write.
apps/api/app/main.py:171:    application.include_router(admin_reference_data_router, prefix="/api/admin")
apps/api/app/main.py:172:    # Identity, BEFORE a tenant has been chosen.
apps/api/app/main.py:173:    #
apps/api/app/main.py:174:    # 🔴 The only authenticated route that does not require
apps/api/app/main.py:175:    # X-Organization-Id. Everything else depends on get_principal, which
apps/api/app/main.py:176:    # demands it -- so without this a browser that had just signed in had
apps/api/app/main.py:177:    # a valid token and no way to discover a tenant to ask for. See
apps/api/app/main.py:178:    # app/api/me.py and migration 024.
apps/api/app/main.py:179:    application.include_router(me_router, prefix="/api/me")
apps/api/app/main.py:180:    application.include_router(projects_router, prefix="/api/projects")
apps/api/app/main.py:181:    application.include_router(opportunities_router, prefix="/api/opportunities")
apps/api/app/main.py:182:    # My Work. Mounted at its own prefix rather than under /api/projects
apps/api/app/main.py:183:    # because a task need not belong to a project at all.
apps/api/app/main.py:184:    application.include_router(tasks_router, prefix="/api/my-work")
apps/api/app/main.py:185:    # Slice 3. Materials and suppliers are ORGANIZATION-scoped reference
apps/api/app/main.py:186:    # data, so they sit at the top level rather than under a project --
apps/api/app/main.py:187:    # a chemist on any project must be able to see the whole library.
apps/api/app/main.py:188:    application.include_router(materials_router, prefix="/api/materials")
apps/api/app/main.py:189:    application.include_router(suppliers_router, prefix="/api/suppliers")
apps/api/app/main.py:190:    # Formulations ARE project-scoped, but they are addressed by their own
apps/api/app/main.py:191:    # id and RLS applies the project-membership predicate to every row, so
apps/api/app/main.py:192:    # the prefix carries no project segment. See the module docstring.
apps/api/app/main.py:193:    application.include_router(formulations_router, prefix="/api/formulations")
apps/api/app/main.py:194:    # Slice 4. Batches are project-scoped and addressed by their own id,
apps/api/app/main.py:195:    # like formulations: RLS applies the project-membership predicate to
apps/api/app/main.py:196:    # every row, so the prefix carries no project segment.
apps/api/app/main.py:197:    application.include_router(laboratory_router, prefix="/api/laboratory/batches")
apps/api/app/main.py:198:    # Slice 5. The Test Module. Project-scoped through the sample the test
apps/api/app/main.py:199:    # was taken from, so RLS applies the membership predicate to every row
apps/api/app/main.py:200:    # and the prefix carries no project segment.
apps/api/app/main.py:201:    application.include_router(testing_router, prefix="/api/testing/tests")
apps/api/app/main.py:202:    # Slice 6. Failure investigation, and the ONE shared approval engine —
apps/api/app/main.py:203:    # polymorphic over (entity_type, entity_id) so Validation, Pilot,
apps/api/app/main.py:204:    # Qualification and Release add zero approval infrastructure (§9).
apps/api/app/main.py:205:    application.include_router(failures_router, prefix="/api/quality/failures")
apps/api/app/main.py:206:    application.include_router(approvals_router, prefix="/api/approvals")
apps/api/app/main.py:207:    # Messaging is mounted last because it is the layer every other
apps/api/app/main.py:208:    # domain links INTO -- a thread hangs off a formula, a batch, a
apps/api/app/main.py:209:    # failure -- and nothing in it is a prerequisite for them.
apps/api/app/main.py:210:    application.include_router(messaging_router, prefix="/api/messaging", tags=["messaging"])
apps/api/app/main.py:211:
apps/api/app/main.py:212:    if settings.metrics_enabled:
apps/api/app/main.py:213:
apps/api/app/main.py:214:        @application.get("/metrics", include_in_schema=False)
apps/api/app/main.py:215:        async def metrics() -> Response:
apps/api/app/main.py:216:            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
apps/api/app/main.py:217:
apps/api/app/main.py:218:    return application
apps/api/app/main.py:219:
apps/api/app/main.py:220:
apps/api/app/main.py:221:app = create_app()

codex
A concrete availability issue is emerging in observability: the middleware computes the Prometheus path label before routing occurs, so arbitrary request paths can create unbounded time series. I’m now checking whether sensitive state-changing endpoints have similar enforcement gaps or whether their service layer closes them.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n -C 18 \"Depends\\(get_principal\\)\" apps/api/app/api/testing.py apps/api/app/api/laboratory.py apps/api/app/api/materials.py apps/api/app/api/tasks.py apps/api/app/api/messaging.py; rg -n \"def (record_decision|review_batch|change_material_status|claim_task|complete_task|open_channel|post_message)|PermissionDenied|permission|principal\\.has|permissions\" apps/api/app/domains apps/api/app/api/testing.py apps/api/app/api/laboratory.py apps/api/app/api/materials.py" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 405ms:
apps/api/app/api/testing.py-320-    """
apps/api/app/api/testing.py-321-    try:
apps/api/app/api/testing.py-322-        return complete_execution(
apps/api/app/api/testing.py-323-            session,
apps/api/app/api/testing.py-324-            test_id=test_id,
apps/api/app/api/testing.py-325-            organization_id=principal.organization_id,
apps/api/app/api/testing.py-326-            actor_id=principal.user_id,
apps/api/app/api/testing.py-327-        )
apps/api/app/api/testing.py-328-    except TestNotFoundError as exc:
apps/api/app/api/testing.py-329-        raise _missing(exc) from exc
apps/api/app/api/testing.py-330-    except TestStateError as exc:
apps/api/app/api/testing.py-331-        raise _conflict(exc) from exc
apps/api/app/api/testing.py-332-
apps/api/app/api/testing.py-333-
apps/api/app/api/testing.py-334-@router.post("/{test_id}/decisions", status_code=status.HTTP_201_CREATED, tags=["testing"])
apps/api/app/api/testing.py-335-def post_decision(
apps/api/app/api/testing.py-336-    test_id: uuid.UUID,
apps/api/app/api/testing.py-337-    payload: DecisionCreate,
apps/api/app/api/testing.py:338:    principal: Principal = Depends(get_principal),
apps/api/app/api/testing.py-339-    session: Session = Depends(get_db),
apps/api/app/api/testing.py-340-) -> dict[str, Any]:
apps/api/app/api/testing.py-341-    """Record a review or approval decision.
apps/api/app/api/testing.py-342-
apps/api/app/api/testing.py-343-    Depends on `get_principal` because the required permission depends on
apps/api/app/api/testing.py-344-    the STAGE and the AUTHORITY LEVEL in the body. A single permission on
apps/api/app/api/testing.py-345-    the endpoint would either let a Chemist supply a director-level
apps/api/app/api/testing.py-346-    approval, or stop the Director supplying a development one.
apps/api/app/api/testing.py-347-
apps/api/app/api/testing.py-348-    A 403 here can mean two different things and says which: the caller
apps/api/app/api/testing.py-349-    lacks the permission, or the caller holds it and is barred on THIS
apps/api/app/api/testing.py-350-    test by their own earlier involvement (ADR-019).
apps/api/app/api/testing.py-351-    """
apps/api/app/api/testing.py-352-    if payload.stage == "review":
apps/api/app/api/testing.py-353-        required = "test.review"
apps/api/app/api/testing.py-354-    else:
apps/api/app/api/testing.py-355-        authority = payload.authority_level
apps/api/app/api/testing.py-356-        if authority is None:
--
apps/api/app/api/tasks.py-81-def _refuse(exc: Exception) -> HTTPException:
apps/api/app/api/tasks.py-82-    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
apps/api/app/api/tasks.py-83-
apps/api/app/api/tasks.py-84-
apps/api/app/api/tasks.py-85-def _bad_reference(exc: CrossTenantReferenceError) -> HTTPException:
apps/api/app/api/tasks.py-86-    """400, not 403 or 404.
apps/api/app/api/tasks.py-87-
apps/api/app/api/tasks.py-88-    The caller named a user who is not a member of this organization. 403
apps/api/app/api/tasks.py-89-    would imply the id is real and merely off-limits; 404 would imply it
apps/api/app/api/tasks.py-90-    is not real. Both leak. 400 says only that the payload was wrong,
apps/api/app/api/tasks.py-91-    which is all the caller is entitled to know.
apps/api/app/api/tasks.py-92-    """
apps/api/app/api/tasks.py-93-    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
apps/api/app/api/tasks.py-94-
apps/api/app/api/tasks.py-95-
apps/api/app/api/tasks.py-96-@router.get("", tags=["my-work"])
apps/api/app/api/tasks.py-97-def list_my_work(
apps/api/app/api/tasks.py-98-    include_done: bool = Query(default=False),
apps/api/app/api/tasks.py:99:    principal: Principal = Depends(get_principal),
apps/api/app/api/tasks.py-100-    session: Session = Depends(get_db),
apps/api/app/api/tasks.py-101-) -> list[dict[str, Any]]:
apps/api/app/api/tasks.py-102-    """The caller's inbox, most urgent first."""
apps/api/app/api/tasks.py-103-    return my_work(
apps/api/app/api/tasks.py-104-        session,
apps/api/app/api/tasks.py-105-        user_id=principal.user_id,
apps/api/app/api/tasks.py-106-        organization_id=principal.organization_id,
apps/api/app/api/tasks.py-107-        role_codes=principal.roles,
apps/api/app/api/tasks.py-108-        include_done=include_done,
apps/api/app/api/tasks.py-109-    )
apps/api/app/api/tasks.py-110-
apps/api/app/api/tasks.py-111-
apps/api/app/api/tasks.py-112-@router.get("/counts", tags=["my-work"])
apps/api/app/api/tasks.py-113-def get_my_work_counts(
apps/api/app/api/tasks.py:114:    principal: Principal = Depends(get_principal),
apps/api/app/api/tasks.py-115-    session: Session = Depends(get_db),
apps/api/app/api/tasks.py-116-) -> dict[str, int]:
apps/api/app/api/tasks.py-117-    """Sidebar badge numbers.
apps/api/app/api/tasks.py-118-
apps/api/app/api/tasks.py-119-    Actionable items only (CLAUDE.md §11). Built from the same predicate
apps/api/app/api/tasks.py-120-    as the list above, so the badge and the inbox can never disagree.
apps/api/app/api/tasks.py-121-    """
apps/api/app/api/tasks.py-122-    return my_work_counts(
apps/api/app/api/tasks.py-123-        session,
apps/api/app/api/tasks.py-124-        user_id=principal.user_id,
apps/api/app/api/tasks.py-125-        organization_id=principal.organization_id,
apps/api/app/api/tasks.py-126-        role_codes=principal.roles,
apps/api/app/api/tasks.py-127-    )
apps/api/app/api/tasks.py-128-
apps/api/app/api/tasks.py-129-
apps/api/app/api/tasks.py-130-@router.post("", status_code=status.HTTP_201_CREATED, tags=["my-work"])
apps/api/app/api/tasks.py-131-def post_task(
apps/api/app/api/tasks.py-132-    payload: TaskCreate,
--
apps/api/app/api/tasks.py-149-                source_event="manual",
apps/api/app/api/tasks.py-150-                entity_type=payload.entity_type,
apps/api/app/api/tasks.py-151-                entity_id=payload.entity_id,
apps/api/app/api/tasks.py-152-                required_action=payload.required_action,
apps/api/app/api/tasks.py-153-            ),
apps/api/app/api/tasks.py-154-            actor_id=principal.user_id,
apps/api/app/api/tasks.py-155-            organization_id=principal.organization_id,
apps/api/app/api/tasks.py-156-        )
apps/api/app/api/tasks.py-157-    except CrossTenantReferenceError as exc:
apps/api/app/api/tasks.py-158-        raise _bad_reference(exc) from exc
apps/api/app/api/tasks.py-159-    except TaskStateError as exc:
apps/api/app/api/tasks.py-160-        raise _refuse(exc) from exc
apps/api/app/api/tasks.py-161-    return {"id": str(task_id)}
apps/api/app/api/tasks.py-162-
apps/api/app/api/tasks.py-163-
apps/api/app/api/tasks.py-164-@router.post("/{task_id}/claim", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
apps/api/app/api/tasks.py-165-def post_claim(
apps/api/app/api/tasks.py-166-    task_id: uuid.UUID,
apps/api/app/api/tasks.py:167:    principal: Principal = Depends(get_principal),
apps/api/app/api/tasks.py-168-    session: Session = Depends(get_db),
apps/api/app/api/tasks.py-169-) -> None:
apps/api/app/api/tasks.py-170-    """Take a role-addressed task.
apps/api/app/api/tasks.py-171-
apps/api/app/api/tasks.py-172-    No permission check: the service refuses any task not addressed to a
apps/api/app/api/tasks.py-173-    role the caller holds, which is a stronger condition than any
apps/api/app/api/tasks.py-174-    permission grant could express.
apps/api/app/api/tasks.py-175-    """
apps/api/app/api/tasks.py-176-    try:
apps/api/app/api/tasks.py-177-        claim_task(
apps/api/app/api/tasks.py-178-            session,
apps/api/app/api/tasks.py-179-            task_id=task_id,
apps/api/app/api/tasks.py-180-            user_id=principal.user_id,
apps/api/app/api/tasks.py-181-            organization_id=principal.organization_id,
apps/api/app/api/tasks.py-182-            role_codes=principal.roles,
apps/api/app/api/tasks.py-183-        )
apps/api/app/api/tasks.py-184-    except TaskStateError as exc:
apps/api/app/api/tasks.py-185-        raise _refuse(exc) from exc
apps/api/app/api/tasks.py-186-
apps/api/app/api/tasks.py-187-
apps/api/app/api/tasks.py-188-@router.post("/{task_id}/complete", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
apps/api/app/api/tasks.py-189-def post_complete(
apps/api/app/api/tasks.py-190-    task_id: uuid.UUID,
apps/api/app/api/tasks.py-191-    payload: TaskComplete,
apps/api/app/api/tasks.py:192:    principal: Principal = Depends(get_principal),
apps/api/app/api/tasks.py-193-    session: Session = Depends(get_db),
apps/api/app/api/tasks.py-194-) -> None:
apps/api/app/api/tasks.py-195-    """Mark the caller's own task done. The service refuses anyone else's."""
apps/api/app/api/tasks.py-196-    try:
apps/api/app/api/tasks.py-197-        complete_task(
apps/api/app/api/tasks.py-198-            session,
apps/api/app/api/tasks.py-199-            task_id=task_id,
apps/api/app/api/tasks.py-200-            actor_id=principal.user_id,
apps/api/app/api/tasks.py-201-            organization_id=principal.organization_id,
apps/api/app/api/tasks.py-202-            outcome_note=payload.outcome_note,
apps/api/app/api/tasks.py-203-        )
apps/api/app/api/tasks.py-204-    except TaskNotFoundError as exc:
apps/api/app/api/tasks.py-205-        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
apps/api/app/api/tasks.py-206-    except TaskStateError as exc:
apps/api/app/api/tasks.py-207-        raise _refuse(exc) from exc
apps/api/app/api/tasks.py-208-
apps/api/app/api/tasks.py-209-
apps/api/app/api/tasks.py-210-@router.post("/{task_id}/reassign", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
--
apps/api/app/api/laboratory.py-361-    """Close execution. Refused while any line is unweighed."""
apps/api/app/api/laboratory.py-362-    try:
apps/api/app/api/laboratory.py-363-        return complete_batch(
apps/api/app/api/laboratory.py-364-            session,
apps/api/app/api/laboratory.py-365-            batch_id=batch_id,
apps/api/app/api/laboratory.py-366-            organization_id=principal.organization_id,
apps/api/app/api/laboratory.py-367-            actor_id=principal.user_id,
apps/api/app/api/laboratory.py-368-        )
apps/api/app/api/laboratory.py-369-    except BatchNotFoundError as exc:
apps/api/app/api/laboratory.py-370-        raise _missing(exc) from exc
apps/api/app/api/laboratory.py-371-    except BatchStateError as exc:
apps/api/app/api/laboratory.py-372-        raise _conflict(exc) from exc
apps/api/app/api/laboratory.py-373-
apps/api/app/api/laboratory.py-374-
apps/api/app/api/laboratory.py-375-@router.post("/{batch_id}/review", tags=["laboratory"])
apps/api/app/api/laboratory.py-376-def post_review(
apps/api/app/api/laboratory.py-377-    batch_id: uuid.UUID,
apps/api/app/api/laboratory.py-378-    payload: ReviewCreate,
apps/api/app/api/laboratory.py:379:    principal: Principal = Depends(get_principal),
apps/api/app/api/laboratory.py-380-    session: Session = Depends(get_db),
apps/api/app/api/laboratory.py-381-) -> dict[str, Any]:
apps/api/app/api/laboratory.py-382-    """Chemist Review: Accept for Testing, or Reject for Process Deviation.
apps/api/app/api/laboratory.py-383-
apps/api/app/api/laboratory.py-384-    Depends on `get_principal` because the required permission depends on
apps/api/app/api/laboratory.py-385-    the DECISION: only the Engineer holds `batch.reject`. A single
apps/api/app/api/laboratory.py-386-    permission on the endpoint would either hand the Technician a
apps/api/app/api/laboratory.py-387-    rejection right the model withholds, or stop the Engineer accepting.
apps/api/app/api/laboratory.py-388-    """
apps/api/app/api/laboratory.py-389-    required = REVIEW_PERMISSION[payload.decision]
apps/api/app/api/laboratory.py-390-    if not principal.has(required):
apps/api/app/api/laboratory.py-391-        raise PermissionDenied()
apps/api/app/api/laboratory.py-392-
apps/api/app/api/laboratory.py-393-    try:
apps/api/app/api/laboratory.py-394-        return review_batch(
apps/api/app/api/laboratory.py-395-            session,
apps/api/app/api/laboratory.py-396-            batch_id=batch_id,
apps/api/app/api/laboratory.py-397-            organization_id=principal.organization_id,
--
apps/api/app/api/messaging.py-61-    project_id: uuid.UUID
apps/api/app/api/messaging.py-62-
apps/api/app/api/messaging.py-63-
apps/api/app/api/messaging.py-64-class MessagePost(BaseModel):
apps/api/app/api/messaging.py-65-    # 4000 characters, not unbounded. A message is a message; a 2MB paste
apps/api/app/api/messaging.py-66-    # belongs in an attachment, where it can be versioned and scanned.
apps/api/app/api/messaging.py-67-    body: str = Field(min_length=1, max_length=4000)
apps/api/app/api/messaging.py-68-    reply_to_id: uuid.UUID | None = None
apps/api/app/api/messaging.py-69-
apps/api/app/api/messaging.py-70-
apps/api/app/api/messaging.py-71-class MessagePromote(BaseModel):
apps/api/app/api/messaging.py-72-    task_type: str = Field(max_length=50)
apps/api/app/api/messaging.py-73-    title: str = Field(min_length=1, max_length=200)
apps/api/app/api/messaging.py-74-    assigned_user_id: uuid.UUID | None = None
apps/api/app/api/messaging.py-75-
apps/api/app/api/messaging.py-76-
apps/api/app/api/messaging.py-77-@router.get("/channels", summary="Channels this user can see")
apps/api/app/api/messaging.py-78-def get_channels(
apps/api/app/api/messaging.py:79:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-80-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-81-    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py-82-) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py-83-    return list_channels(
apps/api/app/api/messaging.py-84-        session,
apps/api/app/api/messaging.py-85-        organization_id=principal.organization_id,
apps/api/app/api/messaging.py-86-        actor_id=principal.user_id,
apps/api/app/api/messaging.py-87-        limit=limit,
apps/api/app/api/messaging.py-88-    )
apps/api/app/api/messaging.py-89-
apps/api/app/api/messaging.py-90-
apps/api/app/api/messaging.py-91-@router.post("/channels", status_code=status.HTTP_201_CREATED, summary="Open a channel")
apps/api/app/api/messaging.py-92-def post_channel(
apps/api/app/api/messaging.py-93-    payload: ChannelCreate,
apps/api/app/api/messaging.py:94:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-95-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-96-) -> dict[str, Any]:
apps/api/app/api/messaging.py-97-    try:
apps/api/app/api/messaging.py-98-        result = create_channel(
apps/api/app/api/messaging.py-99-            session,
apps/api/app/api/messaging.py-100-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-101-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-102-            spec=ChannelInput(
apps/api/app/api/messaging.py-103-                channel_type=payload.channel_type,
apps/api/app/api/messaging.py-104-                name=payload.name,
apps/api/app/api/messaging.py-105-                project_id=payload.project_id,
apps/api/app/api/messaging.py-106-                entity_type=payload.entity_type,
apps/api/app/api/messaging.py-107-                entity_id=payload.entity_id,
apps/api/app/api/messaging.py-108-                member_ids=tuple(payload.member_ids),
apps/api/app/api/messaging.py-109-            ),
apps/api/app/api/messaging.py-110-        )
apps/api/app/api/messaging.py-111-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-112-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-113-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-114-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-115-    session.commit()
apps/api/app/api/messaging.py-116-    return result
apps/api/app/api/messaging.py-117-
apps/api/app/api/messaging.py-118-
apps/api/app/api/messaging.py-119-@router.post("/threads", summary="The discussion thread for a record, opening one if needed")
apps/api/app/api/messaging.py-120-def open_thread(
apps/api/app/api/messaging.py-121-    payload: ThreadOpen,
apps/api/app/api/messaging.py:122:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-123-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-124-) -> dict[str, Any]:
apps/api/app/api/messaging.py-125-    """Idempotent.
apps/api/app/api/messaging.py-126-
apps/api/app/api/messaging.py-127-    Every "discuss this" button can call it without checking first, which
apps/api/app/api/messaging.py-128-    is the only way a record ends up with one thread rather than six.
apps/api/app/api/messaging.py-129-    """
apps/api/app/api/messaging.py-130-    try:
apps/api/app/api/messaging.py-131-        result = thread_for_record(
apps/api/app/api/messaging.py-132-            session,
apps/api/app/api/messaging.py-133-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-134-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-135-            entity_type=payload.entity_type,
apps/api/app/api/messaging.py-136-            entity_id=payload.entity_id,
apps/api/app/api/messaging.py-137-            project_id=payload.project_id,
apps/api/app/api/messaging.py-138-        )
apps/api/app/api/messaging.py-139-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-140-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-141-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-142-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-143-    session.commit()
apps/api/app/api/messaging.py-144-    return result
apps/api/app/api/messaging.py-145-
apps/api/app/api/messaging.py-146-
apps/api/app/api/messaging.py-147-@router.get("/channels/{channel_id}/messages", summary="A channel's messages")
apps/api/app/api/messaging.py-148-def get_messages(
apps/api/app/api/messaging.py-149-    channel_id: uuid.UUID,
apps/api/app/api/messaging.py:150:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-151-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-152-    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py-153-) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py-154-    return list_messages(
apps/api/app/api/messaging.py-155-        session,
apps/api/app/api/messaging.py-156-        channel_id=channel_id,
apps/api/app/api/messaging.py-157-        organization_id=principal.organization_id,
apps/api/app/api/messaging.py-158-        limit=limit,
apps/api/app/api/messaging.py-159-    )
apps/api/app/api/messaging.py-160-
apps/api/app/api/messaging.py-161-
apps/api/app/api/messaging.py-162-@router.post(
apps/api/app/api/messaging.py-163-    "/channels/{channel_id}/messages",
apps/api/app/api/messaging.py-164-    status_code=status.HTTP_201_CREATED,
apps/api/app/api/messaging.py-165-    summary="Post a message, resolving #references and @mentions",
apps/api/app/api/messaging.py-166-)
apps/api/app/api/messaging.py-167-def post_channel_message(
apps/api/app/api/messaging.py-168-    channel_id: uuid.UUID,
apps/api/app/api/messaging.py-169-    payload: MessagePost,
apps/api/app/api/messaging.py:170:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-171-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-172-) -> dict[str, Any]:
apps/api/app/api/messaging.py-173-    try:
apps/api/app/api/messaging.py-174-        result = post_message(
apps/api/app/api/messaging.py-175-            session,
apps/api/app/api/messaging.py-176-            channel_id=channel_id,
apps/api/app/api/messaging.py-177-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-178-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-179-            spec=MessageInput(body=payload.body, reply_to_id=payload.reply_to_id),
apps/api/app/api/messaging.py-180-        )
apps/api/app/api/messaging.py-181-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-182-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-183-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-184-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-185-    session.commit()
apps/api/app/api/messaging.py-186-    return result
apps/api/app/api/messaging.py-187-
apps/api/app/api/messaging.py-188-
--
apps/api/app/api/messaging.py-209-            session,
apps/api/app/api/messaging.py-210-            message_id=message_id,
apps/api/app/api/messaging.py-211-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-212-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-213-            task_type=payload.task_type,
apps/api/app/api/messaging.py-214-            title=payload.title,
apps/api/app/api/messaging.py-215-            assigned_user_id=payload.assigned_user_id,
apps/api/app/api/messaging.py-216-        )
apps/api/app/api/messaging.py-217-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-218-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-219-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-220-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-221-    session.commit()
apps/api/app/api/messaging.py-222-    return result
apps/api/app/api/messaging.py-223-
apps/api/app/api/messaging.py-224-
apps/api/app/api/messaging.py-225-@router.get("/notifications", summary="This user's notifications")
apps/api/app/api/messaging.py-226-def get_notifications(
apps/api/app/api/messaging.py:227:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-228-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-229-    unread_only: bool = Query(default=False),
apps/api/app/api/messaging.py-230-    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py-231-) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py-232-    return my_notifications(
apps/api/app/api/messaging.py-233-        session,
apps/api/app/api/messaging.py-234-        organization_id=principal.organization_id,
apps/api/app/api/messaging.py-235-        recipient_id=principal.user_id,
apps/api/app/api/messaging.py-236-        unread_only=unread_only,
apps/api/app/api/messaging.py-237-        limit=limit,
apps/api/app/api/messaging.py-238-    )
apps/api/app/api/messaging.py-239-
apps/api/app/api/messaging.py-240-
apps/api/app/api/messaging.py-241-@router.post("/notifications/{notification_id}/read", summary="Mark one as read")
apps/api/app/api/messaging.py-242-def post_notification_read(
apps/api/app/api/messaging.py-243-    notification_id: uuid.UUID,
apps/api/app/api/messaging.py:244:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-245-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-246-) -> dict[str, Any]:
apps/api/app/api/messaging.py-247-    """`recipient_id` comes from the token, never the request.
apps/api/app/api/messaging.py-248-
apps/api/app/api/messaging.py-249-    A caller therefore cannot mark somebody else's notification read and
apps/api/app/api/messaging.py-250-    hide it, silently and permanently, from the person who needed to act.
apps/api/app/api/messaging.py-251-    """
apps/api/app/api/messaging.py-252-    try:
apps/api/app/api/messaging.py-253-        result = mark_notification_read(
apps/api/app/api/messaging.py-254-            session,
apps/api/app/api/messaging.py-255-            notification_id=notification_id,
apps/api/app/api/messaging.py-256-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-257-            recipient_id=principal.user_id,
apps/api/app/api/messaging.py-258-        )
apps/api/app/api/messaging.py-259-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-260-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-261-    session.commit()
apps/api/app/api/messaging.py-262-    return result
--
apps/api/app/api/materials.py-262-    try:
apps/api/app/api/materials.py-263-        return update_material(
apps/api/app/api/materials.py-264-            session,
apps/api/app/api/materials.py-265-            material_id=material_id,
apps/api/app/api/materials.py-266-            organization_id=principal.organization_id,
apps/api/app/api/materials.py-267-            actor_id=principal.user_id,
apps/api/app/api/materials.py-268-            spec=payload.to_input(),
apps/api/app/api/materials.py-269-        )
apps/api/app/api/materials.py-270-    except MaterialNotFoundError as exc:
apps/api/app/api/materials.py-271-        raise _missing(exc) from exc
apps/api/app/api/materials.py-272-    except (MaterialInvalidError, CrossTenantReferenceError) as exc:
apps/api/app/api/materials.py-273-        raise _invalid(exc) from exc
apps/api/app/api/materials.py-274-
apps/api/app/api/materials.py-275-
apps/api/app/api/materials.py-276-@router.post("/{material_id}/status", tags=["materials"])
apps/api/app/api/materials.py-277-def post_material_status(
apps/api/app/api/materials.py-278-    material_id: uuid.UUID,
apps/api/app/api/materials.py-279-    payload: MaterialStatusChange,
apps/api/app/api/materials.py:280:    principal: Principal = Depends(get_principal),
apps/api/app/api/materials.py-281-    session: Session = Depends(get_db),
apps/api/app/api/materials.py-282-) -> dict[str, Any]:
apps/api/app/api/materials.py-283-    """Move a material through its lifecycle.
apps/api/app/api/materials.py-284-
apps/api/app/api/materials.py-285-    Depends on `get_principal` rather than on a single
apps/api/app/api/materials.py-286-    `require_permission(...)` because the required authority depends on
apps/api/app/api/materials.py-287-    BOTH ends of the move -- promoting to `preferred` needs
apps/api/app/api/materials.py-288-    `material.approve_production`, while lifting a restriction needs
apps/api/app/api/materials.py-289-    `material.restrict` no matter where it lands. A single permission on
apps/api/app/api/materials.py-290-    the endpoint would mean whoever may make any status change may make
apps/api/app/api/materials.py-291-    every status change.
apps/api/app/api/materials.py-292-
apps/api/app/api/materials.py-293-    The permission set is handed to the service, which resolves it against
apps/api/app/api/materials.py-294-    the edge table inside the UPDATE's own WHERE clause. So authorization
apps/api/app/api/materials.py-295-    and the write are the same statement, and there is no window between
apps/api/app/api/materials.py-296-    "may they?" and the row moving.
apps/api/app/api/materials.py-297-    """
apps/api/app/api/materials.py-298-    try:
apps/api/app/api/laboratory.py:3:**Each step is guarded by the permission that names it**, and those
apps/api/app/api/laboratory.py:4:permissions were checked against migration 002 before this module was
apps/api/app/api/laboratory.py:13:There is deliberately no `batch.authorize`: no such permission exists, and
apps/api/app/api/laboratory.py:19:**Review is one endpoint, two permissions.** Accepting needs
apps/api/app/api/laboratory.py:22:Technician a rejection right the permission model withholds, or blocked
apps/api/app/api/laboratory.py:38:    PermissionDenied,
apps/api/app/api/laboratory.py:42:    require_permission,
apps/api/app/api/laboratory.py:71:# Which permission each review decision requires. A table for the same
apps/api/app/api/laboratory.py:144:    principal: Principal = Depends(require_permission("batch.view")),
apps/api/app/api/laboratory.py:164:    principal: Principal = Depends(require_permission("batch.create")),
apps/api/app/api/laboratory.py:199:    principal: Principal = Depends(require_permission("batch.view")),
apps/api/app/api/laboratory.py:213:    principal: Principal = Depends(require_permission("batch.create")),
apps/api/app/api/laboratory.py:233:    principal: Principal = Depends(require_permission("batch.execute")),
apps/api/app/api/laboratory.py:254:    principal: Principal = Depends(require_permission("batch.execute")),
apps/api/app/api/laboratory.py:288:    principal: Principal = Depends(require_permission("batch.execute")),
apps/api/app/api/laboratory.py:314:    principal: Principal = Depends(require_permission("batch.execute", "batch.complete")),
apps/api/app/api/laboratory.py:334:    principal: Principal = Depends(require_permission("sample.create")),
apps/api/app/api/laboratory.py:358:    principal: Principal = Depends(require_permission("batch.complete")),
apps/api/app/api/laboratory.py:384:    Depends on `get_principal` because the required permission depends on
apps/api/app/api/laboratory.py:386:    permission on the endpoint would either hand the Technician a
apps/api/app/api/laboratory.py:390:    if not principal.has(required):
apps/api/app/api/laboratory.py:391:        raise PermissionDenied()
apps/api/app/api/laboratory.py:410:        raise PermissionDenied(str(exc)) from exc
apps/api/app/api/materials.py:3:**Status changes are permission-routed, not free.** `material.create` does
apps/api/app/api/materials.py:7:endpoint resolves the permission FROM the requested status rather than
apps/api/app/api/materials.py:9:`require_permission("material.edit")` on a status route would hand every
apps/api/app/api/materials.py:28:from app.core.security import PermissionDenied, Principal, get_db, get_principal, require_permission
apps/api/app/api/materials.py:198:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api/materials.py:214:    principal: Principal = Depends(require_permission("material.create")),
apps/api/app/api/materials.py:236:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api/materials.py:251:    principal: Principal = Depends(require_permission("material.edit")),
apps/api/app/api/materials.py:286:    `require_permission(...)` because the required authority depends on
apps/api/app/api/materials.py:289:    `material.restrict` no matter where it lands. A single permission on
apps/api/app/api/materials.py:293:    The permission set is handed to the service, which resolves it against
apps/api/app/api/materials.py:304:            held_permissions=principal.permissions,
apps/api/app/api/materials.py:313:        raise PermissionDenied(str(exc)) from exc
apps/api/app/api/materials.py:322:        # BOTH, not either. `require_permission` defaults to ANY, and this
apps/api/app/api/materials.py:329:        require_permission("material.view", "formula.view", require_all=True)
apps/api/app/api/materials.py:348:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api/materials.py:361:    principal: Principal = Depends(require_permission("material.edit", "supplier.manage")),
apps/api/app/api/materials.py:372:    Either permission: the Chemist who owns the material's data and the
apps/api/app/api/materials.py:395:    principal: Principal = Depends(require_permission("supplier.manage")),
apps/api/app/api/materials.py:422:    principal: Principal = Depends(require_permission("material.view")),
apps/api/app/api/materials.py:429:    the maintenance permission to READ would make the material detail page
apps/api/app/api/materials.py:438:    principal: Principal = Depends(require_permission("supplier.manage")),
apps/api/app/api/materials.py:459:    principal: Principal = Depends(require_permission("supplier.manage")),
apps/api/app/api/testing.py:29:The approval endpoint resolves ITS permission from the authority level in
apps/api/app/api/testing.py:31:`require_permission` would either hand the Chemist a director-level
apps/api/app/api/testing.py:47:    PermissionDenied,
apps/api/app/api/testing.py:51:    require_permission,
apps/api/app/api/testing.py:172:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api/testing.py:191:    principal: Principal = Depends(require_permission("test.plan")),
apps/api/app/api/testing.py:213:    principal: Principal = Depends(require_permission("test.view")),
apps/api/app/api/testing.py:232:    principal: Principal = Depends(require_permission("test.execute")),
apps/api/app/api/testing.py:252:    principal: Principal = Depends(require_permission("test.execute")),
apps/api/app/api/testing.py:284:    principal: Principal = Depends(require_permission("test.execute", "test.review")),
apps/api/app/api/testing.py:313:    principal: Principal = Depends(require_permission("test.execute")),
apps/api/app/api/testing.py:343:    Depends on `get_principal` because the required permission depends on
apps/api/app/api/testing.py:344:    the STAGE and the AUTHORITY LEVEL in the body. A single permission on
apps/api/app/api/testing.py:349:    lacks the permission, or the caller holds it and is barred on THIS
apps/api/app/api/testing.py:362:    if not principal.has(required):
apps/api/app/api/testing.py:363:        raise PermissionDenied()
apps/api/app/api/testing.py:382:        raise PermissionDenied(str(exc)) from exc
apps/api/app/api/testing.py:392:    principal: Principal = Depends(require_permission("test.confirm")),
apps/api/app/api/testing.py:398:    migration 019, which closed it as an orphaned permission. The
apps/api/app/domains\laboratory\service.py:634:def review_batch(
apps/api/app/domains\failures\service.py:308:    permission the proposer may not hold — and `failure.investigate` (the
apps/api/app/domains\testing\service.py:82:# The development-side approval permission. Anyone who has decided at this
apps/api/app/domains\testing\service.py:108:    here": the same person holds the permission and is barred by their
apps/api/app/domains\testing\service.py:534:def record_decision(
apps/api/app/domains\testing\service.py:553:    in this product is on permissions and the check is here.
apps/api/app/domains\formulations\service.py:367:    formula's cost. The permission would have been enforced on the
apps/api/app/domains\formulations\service.py:507:    `include_cost` is a permission decision made by the route from
apps/api/app/domains\approvals\service.py:69:    """The caller may not decide THIS step, though they hold the permission.
apps/api/app/domains\approvals\service.py:165:                     permission_required, step_label, is_mandatory,
apps/api/app/domains\approvals\service.py:168:                       s.permission_required, s.step_label, s.is_mandatory,
apps/api/app/domains\approvals\service.py:208:    held_permissions: frozenset[str],
apps/api/app/domains\approvals\service.py:220:    3. the caller holds the permission the STEP requires, not one this
apps/api/app/domains\approvals\service.py:229:                       s.permission_required, s.step_label, s.is_mandatory,
apps/api/app/domains\approvals\service.py:276:    # 3 — the permission the STEP names, not one chosen here.
apps/api/app/domains\approvals\service.py:277:    if step["permission_required"] not in held_permissions:
apps/api/app/domains\approvals\service.py:278:        raise IncompatibleDutyError(f"this step requires {step['permission_required']}")
apps/api/app/domains\approvals\service.py:449:                SELECT id, step_number, parallel_group, permission_required, step_label,
apps/api/app/domains\approvals\service.py:513:    held_permissions: frozenset[str],
apps/api/app/domains\approvals\service.py:524:    if not held_permissions:
apps/api/app/domains\approvals\service.py:530:            SELECT s.id AS step_id, s.step_number, s.step_label, s.permission_required,
apps/api/app/domains\approvals\service.py:539:              AND s.permission_required = ANY(CAST(:permissions AS TEXT[]))
apps/api/app/domains\approvals\service.py:553:            "permissions": sorted(held_permissions),
apps/api/app/domains\tasks\service.py:296:def claim_task(
apps/api/app/domains\tasks\service.py:356:def complete_task(
apps/api/app/domains\tasks\service.py:377:    relies on to justify carrying no permission dependency, which made it
apps/api/app/domains\messaging\service.py:340:def post_message(
apps/api/app/domains\messaging\service.py:477:    said, and editing history to match permissions would be a worse lie
apps/api/app/domains\msd\retrieval.py:9:generation.** AI must never become a permission-bypass channel."
apps/api/app/domains\projects\members.py:3:The permission `project.assign_member` has existed since migration 002
apps/api/app/domains\projects\members.py:140:    permission error.
apps/api/app/domains\projects\dashboard.py:45:    (CLAUDE.md §6, and the reason PermissionDenied does not distinguish
apps/api/app/domains\materials\service.py:119:# The first version of this mapped destination -> permission, and the
apps/api/app/domains\materials\service.py:137:    # Promotion is a two-stage ladder, one permission per rung.
apps/api/app/domains\materials\service.py:325:    would hand that permission to everyone who can create a row.
apps/api/app/domains\materials\service.py:406:    the status is a separate, separately-permissioned decision -- folding
apps/api/app/domains\materials\service.py:516:    held_permissions: frozenset[str],
apps/api/app/domains\materials\service.py:524:    permission they hold (`material.approve_lab`, `approve_production`,
apps/api/app/domains\materials\service.py:557:    #   permitted_sources those the CALLER holds the edge's permission for
apps/api/app/domains\materials\service.py:561:    # who lacks the permission matches no row and changes nothing -- there
apps/api/app/domains\materials\service.py:570:        if TRANSITION_PERMISSION[(source, status)] in held_permissions
apps/api/app/domains\materials\service.py:639:        # only reason the predicate excluded it is the permission on that
apps/api/app/domains\materials\service.py:1086:    that migration 016 and `test_002_roles_permissions.py` were written in

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n -C 5 \"model_validator|is_production|cors_allowed|keycloak_issuer|database_url\" apps/api/app/core/config.py; rg -n \"ports:|environment:|POSTGRES|KEYCLOAK|GARAGE|PASSWORD|SECRET|METRICS|APP_ENV|CORS\" infrastructure/compose/docker-compose.yml render.yaml .env.example; rg -n \"limit: int|Query\\(|offset|page|UploadFile|File\\(|Body\\(|Field\\(\" apps/api/app/api | Select-Object -First 300; rg -n \"session\\.commit\\(\\)\" apps/api/app/api apps/api/app/domains" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 576ms:
35-    app_slug: str = "evercoat-itw-rd"
36-    app_env: Literal["development", "staging", "production"] = "development"
37-
38-    # --- Database -------------------------------------------------------
39-    # No default. The app must never guess a connection string.
40:    database_url: str = Field(..., description="SQLAlchemy URL for the runtime app role")
41-    db_pool_size: int = 10
42-    db_max_overflow: int = 5
43-    db_echo: bool = False
44-
45-    # --- Keycloak -------------------------------------------------------
46:    keycloak_issuer: str = Field(..., description="Realm issuer URL")
47-    keycloak_audience: str = Field(default="evercoat-api")
48-    # JWKS is cached; this bounds how long a revoked signing key stays
49-    # trusted after a realm key rotation.
50-    jwks_cache_seconds: int = 300
51-
--
73-    log_format: Literal["json", "console"] = "json"
74-    log_level: str = "INFO"
75-    metrics_enabled: bool = True
76-
77-    # --- Security -------------------------------------------------------
78:    cors_allowed_origins: list[str] = Field(default_factory=list)
79-
80:    @field_validator("database_url")
81-    @classmethod
82-    def _reject_superuser(cls, v: str) -> str:
83-        """Refuse to start as a database superuser.
84-
85-        Superuser bypasses Row Level Security. Running the application as
--
94-                    "the application must not connect as a database superuser; "
95-                    "use the evercoat_app role, which is subject to FORCE RLS"
96-                )
97-        return v
98-
99:    @field_validator("cors_allowed_origins")
100-    @classmethod
101-    def _no_wildcard_in_prod(cls, v: list[str], info) -> list[str]:  # type: ignore[no-untyped-def]
102-        if "*" in v and info.data.get("app_env") == "production":
103-            raise ValueError("wildcard CORS origin is not permitted in production")
104-        return v
105-
106-    @property
107:    def is_production(self) -> bool:
108-        return self.app_env == "production"
109-
110-
111-@lru_cache(maxsize=1)
112-def get_settings() -> Settings:
render.yaml:43:# non-superuser app role, a reachable Keycloak for `KEYCLOAK_ISSUER`, and
.env.example:14:APP_ENV=development
.env.example:17:POSTGRES_DB=evercoat_itw_rd
.env.example:18:POSTGRES_SUPERUSER=postgres
.env.example:19:POSTGRES_PASSWORD=change-me-superuser
.env.example:20:POSTGRES_PORT=55432
.env.example:27:APP_DB_PASSWORD=change-me-app
.env.example:30:WORKER_DB_PASSWORD=change-me-worker
.env.example:33:KEYCLOAK_DB=keycloak
.env.example:34:KEYCLOAK_ADMIN=admin
.env.example:35:KEYCLOAK_ADMIN_PASSWORD=change-me-keycloak
.env.example:36:KEYCLOAK_PORT=18080
.env.example:37:KEYCLOAK_ISSUER=http://keycloak:8080/realms/evercoat
.env.example:38:KEYCLOAK_AUDIENCE=evercoat-api
.env.example:41:GARAGE_ENDPOINT=http://garage:3900
.env.example:42:GARAGE_BUCKET=evercoat-documents
.env.example:43:GARAGE_ACCESS_KEY=
.env.example:44:GARAGE_SECRET_KEY=
.env.example:65:NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:18080
.env.example:70:METRICS_ENABLED=true
.env.example:73:# Comma-separated. A wildcard is rejected outright when APP_ENV=production.
.env.example:74:CORS_ALLOWED_ORIGINS=http://localhost:13000
infrastructure/compose/docker-compose.yml:34:    environment:
infrastructure/compose/docker-compose.yml:35:      POSTGRES_DB: ${POSTGRES_DB:-evercoat_itw_rd}
infrastructure/compose/docker-compose.yml:36:      POSTGRES_USER: ${POSTGRES_SUPERUSER:-postgres}
infrastructure/compose/docker-compose.yml:37:      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
infrastructure/compose/docker-compose.yml:41:      POSTGRES_INITDB_ARGS: "--locale=C --encoding=UTF8"
infrastructure/compose/docker-compose.yml:48:      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_SUPERUSER:-postgres} -d ${POSTGRES_DB:-evercoat_itw_rd}"]
infrastructure/compose/docker-compose.yml:55:    ports:
infrastructure/compose/docker-compose.yml:56:      - "${POSTGRES_PORT:-55432}:5432"
infrastructure/compose/docker-compose.yml:93:    environment:
infrastructure/compose/docker-compose.yml:94:      KC_BOOTSTRAP_ADMIN_USERNAME: ${KEYCLOAK_ADMIN:-admin}
infrastructure/compose/docker-compose.yml:95:      KC_BOOTSTRAP_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD is required}
infrastructure/compose/docker-compose.yml:97:      KC_DB_URL: jdbc:postgresql://postgres:5432/${KEYCLOAK_DB:-keycloak}
infrastructure/compose/docker-compose.yml:98:      KC_DB_USERNAME: ${POSTGRES_SUPERUSER:-postgres}
infrastructure/compose/docker-compose.yml:99:      KC_DB_PASSWORD: ${POSTGRES_PASSWORD}
infrastructure/compose/docker-compose.yml:117:    ports:
infrastructure/compose/docker-compose.yml:118:      - "${KEYCLOAK_PORT:-18080}:8080"
infrastructure/compose/docker-compose.yml:125:    environment:
infrastructure/compose/docker-compose.yml:129:      DATABASE_URL: postgresql+psycopg://${APP_DB_USER:-evercoat_app}:${APP_DB_PASSWORD:?APP_DB_PASSWORD is required}@postgres:5432/${POSTGRES_DB:-evercoat_itw_rd}
infrastructure/compose/docker-compose.yml:131:      KEYCLOAK_ISSUER: ${KEYCLOAK_ISSUER:-http://keycloak:8080/realms/evercoat}
infrastructure/compose/docker-compose.yml:132:      KEYCLOAK_AUDIENCE: ${KEYCLOAK_AUDIENCE:-evercoat-api}
infrastructure/compose/docker-compose.yml:133:      GARAGE_ENDPOINT: http://garage:3900
infrastructure/compose/docker-compose.yml:134:      APP_ENV: ${APP_ENV:-development}
infrastructure/compose/docker-compose.yml:149:    ports:
infrastructure/compose/docker-compose.yml:162:    environment:
infrastructure/compose/docker-compose.yml:163:      DATABASE_URL: postgresql+psycopg://${WORKER_DB_USER:-evercoat_worker}:${WORKER_DB_PASSWORD:?WORKER_DB_PASSWORD is required}@postgres:5432/${POSTGRES_DB:-evercoat_itw_rd}
infrastructure/compose/docker-compose.yml:165:      APP_ENV: ${APP_ENV:-development}
infrastructure/compose/docker-compose.yml:179:    environment:
infrastructure/compose/docker-compose.yml:184:      NEXT_PUBLIC_KEYCLOAK_URL: ${NEXT_PUBLIC_KEYCLOAK_URL:-http://localhost:18080}
infrastructure/compose/docker-compose.yml:189:    ports:
infrastructure/compose/docker-compose.yml:201:    ports:
apps/api/app/api\failures.py:81:    failure_code: str = Field(min_length=3, max_length=50)
apps/api/app/api\failures.py:82:    title: str = Field(min_length=3, max_length=200)
apps/api/app/api\failures.py:84:    severity: str = Field(default="major", pattern="^(critical|major|minor)$")
apps/api/app/api\failures.py:91:    possible_cause: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:92:    mechanism: str | None = Field(default=None, max_length=2000)
apps/api/app/api\failures.py:93:    confidence: str = Field(default="medium", pattern="^(low|medium|high)$")
apps/api/app/api\failures.py:94:    source: str | None = Field(default=None, max_length=500)
apps/api/app/api\failures.py:98:    origin: str = Field(default="human", pattern="^(human|msd)$")
apps/api/app/api\failures.py:102:    evidence_type: str = Field(
apps/api/app/api\failures.py:106:    summary: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:108:    referenced_entity_type: str | None = Field(
apps/api/app/api\failures.py:112:    source_reference: str | None = Field(default=None, max_length=500)
apps/api/app/api\failures.py:113:    origin: str = Field(default="human", pattern="^(human|msd)$")
apps/api/app/api\failures.py:118:    relationship: str = Field(default="supports", pattern="^(supports|contradicts|inconclusive)$")
apps/api/app/api\failures.py:119:    note: str | None = Field(default=None, max_length=1000)
apps/api/app/api\failures.py:126:    rationale: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:130:    reason: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:134:    action_type: str = Field(
apps/api/app/api\failures.py:137:    description: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:143:    summary: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:147:    driver_type: str = Field(
apps/api/app/api\failures.py:150:    reason: str = Field(min_length=3, max_length=2000)
apps/api/app/api\failures.py:157:    entity_type: str = Field(
apps/api/app/api\failures.py:161:    authority_level: str = Field(
apps/api/app/api\failures.py:167:    decision: str = Field(
apps/api/app/api\failures.py:171:    condition_text: str | None = Field(default=None, max_length=2000)
apps/api/app/api\failures.py:172:    rationale: str | None = Field(default=None, max_length=2000)
apps/api/app/api\failures.py:194:    project_id: uuid.UUID | None = Query(default=None),
apps/api/app/api\failures.py:195:    status_filter: str | None = Query(default=None, alias="status"),
apps/api/app/api\admin_stage_gates.py:74:    stage_code: str = Field(min_length=1, max_length=50, pattern="^[A-Z0-9_]+$")
apps/api/app/api\admin_stage_gates.py:75:    name: str = Field(min_length=1, max_length=100)
apps/api/app/api\admin_stage_gates.py:76:    sequence: int = Field(ge=1, le=999)
apps/api/app/api\admin_stage_gates.py:106:    ordered_stage_ids: list[uuid.UUID] = Field(min_length=1)
apps/api/app/api\admin_stage_gates.py:111:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\admin_reference_data.py:101:    code: str = Field(min_length=1, max_length=50)
apps/api/app/api\admin_reference_data.py:102:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\admin_reference_data.py:107:    quantity_kind: str = Field(min_length=1, max_length=50)
apps/api/app/api\admin_reference_data.py:108:    display_order: int = Field(default=100, ge=0)
apps/api/app/api\admin_reference_data.py:112:    code: str = Field(min_length=1, max_length=50)
apps/api/app/api\admin_reference_data.py:113:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\admin_reference_data.py:115:    display_order: int = Field(default=100, ge=0)
apps/api/app/api\admin.py:53:    roles: list[str] = Field(default_factory=list)
apps/api/app/api\admin.py:63:    keycloak_sub: str = Field(min_length=1, max_length=255)
apps/api/app/api\admin.py:65:    display_name: str = Field(min_length=1, max_length=200)
apps/api/app/api\admin.py:66:    roles: list[str] = Field(default_factory=list)
apps/api/app/api\admin.py:70:    status: str = Field(pattern="^(active|inactive)$")
apps/api/app/api\admin.py:71:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\admin.py:79:    permissions: list[str] = Field(default_factory=list)
apps/api/app/api\admin.py:89:    role_code: str = Field(min_length=1, max_length=100)
apps/api/app/api\admin.py:90:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\testing.py:95:    test_number: str = Field(min_length=3, max_length=50)
apps/api/app/api\testing.py:98:    test_purpose: str = Field(
apps/api/app/api\testing.py:101:    authority_level: str = Field(
apps/api/app/api\testing.py:122:    replicate_number: int = Field(ge=1)
apps/api/app/api\testing.py:127:    unit: str = Field(min_length=1, max_length=20)
apps/api/app/api\testing.py:132:    reason: str = Field(min_length=3, max_length=1000)
apps/api/app/api\testing.py:143:    decision: str = Field(
apps/api/app/api\testing.py:147:    stage: str = Field(default="review", pattern="^(review|approval)$")
apps/api/app/api\testing.py:148:    authority_level: str | None = Field(
apps/api/app/api\testing.py:152:    condition_text: str | None = Field(default=None, max_length=2000)
apps/api/app/api\testing.py:153:    rationale: str | None = Field(default=None, max_length=2000)
apps/api/app/api\testing.py:170:    project_id: uuid.UUID | None = Query(default=None),
apps/api/app/api\testing.py:171:    review_state: str | None = Query(default=None),
apps/api/app/api\me.py:69:    roles: list[str] = Field(default_factory=list)
apps/api/app/api\me.py:78:    organizations: list[OrganizationMembership] = Field(default_factory=list)
apps/api/app/api\tasks.py:57:    task_type: str = Field(min_length=1, max_length=50)
apps/api/app/api\tasks.py:58:    title: str = Field(min_length=1, max_length=200)
apps/api/app/api\tasks.py:60:    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
apps/api/app/api\tasks.py:78:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\tasks.py:98:    include_done: bool = Query(default=False),
apps/api/app/api\materials.py:89:    material_code: str = Field(min_length=2, max_length=50)
apps/api/app/api\materials.py:90:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\materials.py:91:    category: str = Field(min_length=1, max_length=100)
apps/api/app/api\materials.py:92:    role: str = Field(
apps/api/app/api\materials.py:97:    cas_number: str | None = Field(default=None, max_length=50)
apps/api/app/api\materials.py:98:    density_g_cm3: Decimal | None = Field(default=None, gt=0)
apps/api/app/api\materials.py:99:    solids_fraction: Decimal | None = Field(default=None, ge=0, le=1)
apps/api/app/api\materials.py:100:    voc_fraction: Decimal | None = Field(default=None, ge=0, le=1)
apps/api/app/api\materials.py:101:    cost_per_kg: Decimal | None = Field(default=None, ge=0)
apps/api/app/api\materials.py:102:    epoxy_equivalent_weight: Decimal | None = Field(default=None, gt=0)
apps/api/app/api\materials.py:103:    amine_hydrogen_equivalent_weight: Decimal | None = Field(default=None, gt=0)
apps/api/app/api\materials.py:113:    status: str = Field(pattern="^(development|approved|preferred|restricted|obsolete)$")
apps/api/app/api\materials.py:117:    restriction_reason: str | None = Field(default=None, max_length=1000)
apps/api/app/api\materials.py:118:    reason: str = Field(min_length=3, max_length=1000)
apps/api/app/api\materials.py:127:    document_type: str = Field(pattern="^(TDS|SDS|CoA|regulatory|other)$")
apps/api/app/api\materials.py:128:    title: str = Field(min_length=1, max_length=200)
apps/api/app/api\materials.py:129:    storage_key: str = Field(min_length=1, max_length=500)
apps/api/app/api\materials.py:130:    content_type: str | None = Field(default=None, max_length=200)
apps/api/app/api\materials.py:131:    byte_size: int | None = Field(default=None, ge=0)
apps/api/app/api\materials.py:132:    checksum_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
apps/api/app/api\materials.py:142:    supplier_code: str = Field(min_length=2, max_length=50)
apps/api/app/api\materials.py:143:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\materials.py:144:    country: str | None = Field(default=None, max_length=100)
apps/api/app/api\materials.py:145:    quality_rating: str | None = Field(default=None, pattern="^[ABCD]$")
apps/api/app/api\materials.py:155:    status: str = Field(pattern="^(pending|qualified|approved|suspended|disqualified)$")
apps/api/app/api\materials.py:156:    reason: str = Field(min_length=3, max_length=1000)
apps/api/app/api\materials.py:161:    supplier_part_code: str | None = Field(default=None, max_length=100)
apps/api/app/api\materials.py:166:    lead_time_days: int | None = Field(default=None, ge=0)
apps/api/app/api\materials.py:167:    quoted_price_per_kg: Decimal | None = Field(default=None, ge=0)
apps/api/app/api\materials.py:168:    currency: str | None = Field(default=None, max_length=3)
apps/api/app/api\materials.py:195:    status_filter: str | None = Query(default=None, alias="status"),
apps/api/app/api\materials.py:196:    role: str | None = Query(default=None),
apps/api/app/api\materials.py:197:    search: str | None = Query(default=None, max_length=100),
apps/api/app/api\materials.py:421:    status_filter: str | None = Query(default=None, alias="status"),
apps/api/app/api\materials.py:429:    the maintenance permission to READ would make the material detail page
apps/api/app/api\projects.py:95:    project_code: str = Field(min_length=3, max_length=50)
apps/api/app/api\projects.py:96:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\projects.py:101:    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
apps/api/app/api\projects.py:105:    confidentiality: str = Field(default="normal", pattern="^(normal|restricted)$")
apps/api/app/api\projects.py:109:    to_stage_code: str = Field(min_length=1, max_length=50)
apps/api/app/api\projects.py:112:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\projects.py:117:    requirement_code: str = Field(min_length=3, max_length=50)
apps/api/app/api\projects.py:118:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\projects.py:119:    category: str = Field(default="technical")
apps/api/app/api\projects.py:126:    criticality: str = Field(default="major", pattern="^(critical|major|minor|informational)$")
apps/api/app/api\projects.py:127:    verification_method: str = Field(default="test")
apps/api/app/api\projects.py:136:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\projects.py:476:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\projects.py:482:    status: str = Field(pattern="^(planned|in_progress|met|missed|cancelled)$")
apps/api/app/api\projects.py:487:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\projects.py:491:    risk_code: str = Field(min_length=2, max_length=50)
apps/api/app/api\projects.py:492:    title: str = Field(min_length=1, max_length=200)
apps/api/app/api\projects.py:493:    probability: str = Field(pattern="^(low|medium|high)$")
apps/api/app/api\projects.py:494:    impact: str = Field(pattern="^(low|medium|high)$")
apps/api/app/api\projects.py:495:    category: str = Field(
apps/api/app/api\projects.py:512:    status: str | None = Field(default=None, pattern="^(open|mitigating|closed|accepted|realised)$")
apps/api/app/api\projects.py:514:    probability: str | None = Field(default=None, pattern="^(low|medium|high)$")
apps/api/app/api\projects.py:515:    impact: str | None = Field(default=None, pattern="^(low|medium|high)$")
apps/api/app/api\projects.py:517:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\projects.py:683:    project_role: str = Field(pattern="^(lead|chemist|engineer|technician|qa|director|observer)$")
apps/api/app/api\projects.py:687:    reason: str = Field(min_length=3, max_length=500)
apps/api/app/api\messaging.py:48:    channel_type: str = Field(pattern="^(project|direct|technical_thread|announcement)$")
apps/api/app/api\messaging.py:49:    name: str | None = Field(default=None, max_length=200)
apps/api/app/api\messaging.py:51:    entity_type: str | None = Field(default=None, max_length=50)
apps/api/app/api\messaging.py:53:    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
apps/api/app/api\messaging.py:59:    entity_type: str = Field(max_length=50)
apps/api/app/api\messaging.py:67:    body: str = Field(min_length=1, max_length=4000)
apps/api/app/api\messaging.py:72:    task_type: str = Field(max_length=50)
apps/api/app/api\messaging.py:73:    title: str = Field(min_length=1, max_length=200)
apps/api/app/api\messaging.py:81:    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api\messaging.py:152:    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api\messaging.py:229:    unread_only: bool = Query(default=False),
apps/api/app/api\messaging.py:230:    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api\laboratory.py:82:    batch_number: str = Field(min_length=3, max_length=50)
apps/api/app/api\laboratory.py:86:    planned_quantity_kg: Decimal = Field(gt=0)
apps/api/app/api\laboratory.py:87:    tolerance_percent: Decimal | None = Field(default=None, ge=0, le=100)
apps/api/app/api\laboratory.py:88:    purpose: str | None = Field(default=None, max_length=500)
apps/api/app/api\laboratory.py:94:    actual_mass_kg: Decimal = Field(ge=0)
apps/api/app/api\laboratory.py:99:    parameter_code: str = Field(min_length=1, max_length=50)
apps/api/app/api\laboratory.py:104:    unit: str = Field(min_length=1, max_length=20)
apps/api/app/api\laboratory.py:105:    stage: str | None = Field(default=None, max_length=50)
apps/api/app/api\laboratory.py:110:    description: str = Field(min_length=3, max_length=2000)
apps/api/app/api\laboratory.py:111:    severity: str = Field(default="minor", pattern="^(minor|major|critical)$")
apps/api/app/api\laboratory.py:116:    sample_number: str = Field(min_length=3, max_length=50)
apps/api/app/api\laboratory.py:117:    quantity_g: Decimal | None = Field(default=None, gt=0)
apps/api/app/api\laboratory.py:118:    purpose: str | None = Field(default=None, max_length=500)
apps/api/app/api\laboratory.py:119:    storage_location: str | None = Field(default=None, max_length=200)
apps/api/app/api\laboratory.py:124:    decision: str = Field(pattern="^(accept|reject)$")
apps/api/app/api\laboratory.py:125:    note: str | None = Field(default=None, max_length=2000)
apps/api/app/api\laboratory.py:142:    project_id: uuid.UUID | None = Query(default=None),
apps/api/app/api\laboratory.py:143:    status_filter: str | None = Query(default=None, alias="status"),
apps/api/app/api\opportunities.py:44:    opportunity_code: str = Field(min_length=3, max_length=50)
apps/api/app/api\opportunities.py:45:    title: str = Field(min_length=1, max_length=200)
apps/api/app/api\opportunities.py:50:    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
apps/api/app/api\opportunities.py:54:    decision: str = Field(pattern="^(approve|reject|hold|more_information)$")
apps/api/app/api\opportunities.py:57:    rationale: str = Field(min_length=3, max_length=2000)
apps/api/app/api\opportunities.py:61:    project_code: str = Field(min_length=3, max_length=50)
apps/api/app/api\opportunities.py:62:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\opportunities.py:65:    confidentiality: str = Field(default="normal", pattern="^(normal|restricted)$")
apps/api/app/api\opportunities.py:78:    status_filter: str | None = Query(default=None, alias="status"),
apps/api/app/api\formulations.py:63:    formula_code: str = Field(min_length=2, max_length=50)
apps/api/app/api\formulations.py:64:    name: str = Field(min_length=1, max_length=200)
apps/api/app/api\formulations.py:65:    product_family: str | None = Field(default=None, max_length=100)
apps/api/app/api\formulations.py:81:    percentage: Decimal = Field(ge=0, le=100)
apps/api/app/api\formulations.py:82:    role_override: str | None = Field(default=None, pattern=f"^({_ROLES})$")
apps/api/app/api\formulations.py:83:    display_order: int = Field(default=100, ge=0)
apps/api/app/api\formulations.py:90:    components: list[ComponentLine] = Field(min_length=1)
apps/api/app/api\formulations.py:94:    decision: str = Field(pattern="^(approve|reject)$")
apps/api/app/api\formulations.py:95:    note: str | None = Field(default=None, max_length=2000)
apps/api/app/api\formulations.py:102:    change_reason: str = Field(min_length=3, max_length=2000)
apps/api/app/api\formulations.py:103:    technical_hypothesis: str = Field(min_length=3, max_length=2000)
apps/api/app/api\formulations.py:104:    expected_effect: str | None = Field(default=None, max_length=2000)
apps/api/app/api\formulations.py:105:    version_code: str | None = Field(default=None, max_length=50)
apps/api/app/api\formulations.py:109:    observed_effect: str = Field(min_length=3, max_length=2000)
apps/api/app/api\formulations.py:113:    batch_mass_kg: Decimal = Field(gt=0)
apps/api/app/api\formulations.py:130:    project_id: uuid.UUID | None = Query(default=None),
apps/api/app/api\formulations.py:401:    against: uuid.UUID = Query(description="the version to compare against"),
apps/api/app/api\messaging.py:115:    session.commit()
apps/api/app/api\messaging.py:143:    session.commit()
apps/api/app/api\messaging.py:185:    session.commit()
apps/api/app/api\messaging.py:221:    session.commit()
apps/api/app/api\messaging.py:261:    session.commit()

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -C 4 "exp|nbf|iat|missing.*claim|alg|kid|JWKS|metrics|cardinal|Correlation" apps/api/tests SECURITY.md reviews/codex-slice7-messaging-auth.md; rg -n "def list_|SELECT" apps/api/app/domains/materials/service.py apps/api/app/domains/formulations/service.py apps/api/app/domains/laboratory/service.py apps/api/app/domains/testing/service.py apps/api/app/domains/failures/service.py apps/api/app/domains/opportunities/service.py | Select-Object -First 200' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 613ms:
SECURITY.md-1-# SECURITY.md — EvercoatITWRD APP
SECURITY.md-2-
SECURITY.md:3:**Threat premise.** This system holds proprietary chemical formulations, experimental history, supplier terms, failure knowledge and product-development strategy. That data *is* the company's competitive position. It is more valuable than the software, and it is permanently damaging if leaked — a formula cannot be rotated like a password.
SECURITY.md-4-
SECURITY.md-5-Every control below exists to serve one goal: **proprietary formulation IP is protected at the backend and database layers, never by hidden frontend controls.**
SECURITY.md-6-
SECURITY.md-7----
--
SECURITY.md-15-      ↓
SECURITY.md-16-PostgreSQL          Row Level Security on organization_id
SECURITY.md-17-```
SECURITY.md-18-
SECURITY.md:19:**Design requirement: any one layer failing must not expose data.** A bug in a FastAPI dependency must still hit RLS. A misconfigured Keycloak mapping must still hit permission checks.
SECURITY.md-20-
SECURITY.md-21----
SECURITY.md-22-
SECURITY.md-23-## 2. Authentication
SECURITY.md-24-
SECURITY.md-25-- **Keycloak** provides login, logout, SSO, OAuth 2.0, OpenID Connect, JWT, refresh tokens, password policy, optional MFA, session management and identity federation.
SECURITY.md:26:- The API validates JWTs against the realm's published JWKS. **Signature, issuer, audience and expiry are all verified.** Never trust an unverified claim.
SECURITY.md-27-- Access tokens short-lived; refresh handled by the web app; refresh token rotation enabled.
SECURITY.md-28-- No local password storage in the application database. Keycloak owns credentials.
SECURITY.md-29-- Service-to-service calls (workers → API) use a dedicated confidential client, not a human user's token.
SECURITY.md-30-
--
SECURITY.md-37-```
SECURITY.md-38-
SECURITY.md-39-- **Authorize on permissions, never on role names.** `project.create`, `project.assign_member`, `formula.create`, `formula.modify_draft`, `formula.submit`, `formula.approve_lab`, `test.execute`, `test.review`, `test.confirm`, `failure.close`, `product.release`, and so on. Role→permission mapping is data, editable in Administration.
SECURITY.md-40-- **Resource scope** is a separate check from permission. Holding `test.review` does not grant review of a test in a project you are not a member of.
SECURITY.md:41:- **Business rules are the last gate** and are not expressible as permissions: a released formula cannot be edited by anyone; a technically passing test cannot go GREEN with approvals outstanding; the executing user cannot supply all mandatory approvals on a qualification/release test.
SECURITY.md-42-- **Segregation of duties** is enforced server-side for high-authority confirmation tests.
SECURITY.md-43-
SECURITY.md-44-### Frontend permission checks are cosmetic
SECURITY.md-45-Hiding a button is a usability feature, not a security control. Every action is re-authorized server-side. **Playwright tests attempted unauthorized access** — direct API calls and direct URL navigation — not merely that a control is invisible.
--
SECURITY.md-81-- Documents are versioned; a message linking "SDS RM-014 Revision 4" must keep pointing at Revision 4 after the document is revised.
SECURITY.md-82-
SECURITY.md-83-## 7. AI access boundaries — MSD
SECURITY.md-84-
SECURITY.md:85:**MSD operates under exactly the calling user's authorization boundary.** If the user cannot open Formula F100 through the application, MSD must not retrieve, summarize, infer or expose F100 through chat.
SECURITY.md-86-
SECURITY.md-87-The rule that makes this real: **filter before retrieval, never after generation.** Post-hoc filtering is not a control — the model has already seen the data and can leak it through paraphrase, aggregation or inference.
SECURITY.md-88-
SECURITY.md-89-- Every retrieval tool takes the caller's principal and applies the same permission + scope + RLS path as the REST API. Tools do not have their own database credentials.
--
SECURITY.md-113-- Database constraints are the final backstop: check constraints on ranges and enums, unique constraints, NOT NULL, NUMERIC precision.
SECURITY.md-114-
SECURITY.md-115-## 10. Rate limiting and abuse
SECURITY.md-116-
SECURITY.md:117:- Valkey-backed rate limits per user and per IP on: authentication, search, MSD/AI endpoints, report generation, exports and file uploads.
SECURITY.md:118:- AI inference is separately throttled and queued — it is the most expensive endpoint and the easiest to weaponise.
SECURITY.md:119:- Bulk export of formulas or test results is permission-gated **and** audited as a distinct high-sensitivity event.
SECURITY.md-120-
SECURITY.md-121-## 11. Audit logging
SECURITY.md-122-
SECURITY.md-123-`audit.events` is **append-only**: no `UPDATE`, no `DELETE`, unreachable from ordinary application paths, revoked at the role level for the app user.
SECURITY.md-124-
SECURITY.md-125-Each event records: organization · user · role · action · entity type · entity id · previous state · new state · reason · timestamp · session/IP metadata.
SECURITY.md-126-
SECURITY.md:127:Audited actions include: formula creation, revision, submission and approval; test result entry, correction and approval; failure closure; root-cause acceptance; stage transitions; qualification; product release; role and permission changes; document access; bulk export; and every MSD action that touched controlled records.
SECURITY.md-128-
SECURITY.md-129-### Logging security
SECURITY.md-130-Logs must never contain formula compositions, component percentages, secrets, tokens or full request bodies from formulation endpoints. Log identifiers and outcomes, not payloads. Loki retention is bounded.
SECURITY.md-131-
--
SECURITY.md-134-- **SOPS + age.** Encrypted configuration may be committed; plaintext secrets never may.
SECURITY.md-135-- **Gitleaks in CI**, and in pre-commit.
SECURITY.md-136-- Never in Git: database passwords, Keycloak client secrets, signing keys, encryption keys, object-storage keys, SMTP/Resend credentials.
SECURITY.md-137-- Rotation procedure documented in `DEPLOYMENT.md`; rotation does not require a code change.
SECURITY.md:138:- *Operator note:* PowerShell pipelines add a UTF-16 BOM. Write secret files with explicit UTF-8 or the secret silently becomes invalid.
SECURITY.md-139-
SECURITY.md-140-## 13. Transport and production configuration
SECURITY.md-141-
SECURITY.md-142-- **TLS everywhere**, terminated at Caddy with automatic certificates. HTTP redirects to HTTPS.
SECURITY.md-143-- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy without `unsafe-inline` scripts.
SECURITY.md:144:- Only web, api and Keycloak are exposed. **PostgreSQL, Valkey, Garage, the AI runtime and (later) Temporal stay on the internal network** and are never published to the host in production compose.
SECURITY.md-145-- `DEBUG=false`, no stack traces to clients, generic error bodies with a correlation id.
SECURITY.md-146-- Default credentials changed at provisioning; the Keycloak admin console is not publicly reachable.
SECURITY.md-147-
SECURITY.md-148-## 14. Backup protection
--
SECURITY.md-150-- Scheduled `pg_dump` plus Garage snapshots, **encrypted at rest**, with retention policy and offsite copy.
SECURITY.md-151-- **Restore is tested, not assumed** — an untested backup is not a backup. Restore drill is part of the Slice 20 hardening gate.
SECURITY.md-152-- Backups contain the company's entire IP; they are protected at least as strictly as production.
SECURITY.md-153-- Keycloak realm configuration is backed up alongside the database.
SECURITY.md:154:- *Note:* `pg_dump` under FORCE RLS as a non-superuser will silently omit rows it cannot see. The backup role and its policies are explicitly configured and the dump's row counts are verified against source counts.
SECURITY.md-155-
SECURITY.md-156-## 15. Security testing
SECURITY.md-157-
SECURITY.md-158-Automated, in CI:
--
SECURITY.md-169-A high-severity Trivy finding blocks staging deployment. `/security-review` runs as part of the Supervisor gate.
SECURITY.md-170-
SECURITY.md-171-## 16. Incident posture
SECURITY.md-172-
SECURITY.md:173:- Correlation ids on every request, propagated through OpenTelemetry, so an incident can be reconstructed from the audit trail plus traces.
SECURITY.md-174-- The audit trail is the authoritative record of who did what; logs are supporting evidence.
SECURITY.md:175:- Suspected formula exposure is treated as an IP incident: identify affected records via the document-access audit, not by guesswork.
--
apps/api/tests\test_migration_coverage.py-112-
apps/api/tests\test_migration_coverage.py-113-    assert revisions, f"no Alembic revisions parsed from {VERSIONS_DIR}"
apps/api/tests\test_migration_coverage.py-114-    parents = {parent for parent in revisions.values() if parent is not None}
apps/api/tests\test_migration_coverage.py-115-    heads = sorted(set(revisions) - parents)
apps/api/tests\test_migration_coverage.py:116:    assert len(heads) == 1, f"expected exactly one head, found {heads}"
apps/api/tests\test_migration_coverage.py-117-
apps/api/tests\test_migration_coverage.py-118-    orphan_parents = sorted(parents - set(revisions))
apps/api/tests\test_migration_coverage.py-119-    assert not orphan_parents, (
apps/api/tests\test_migration_coverage.py-120-        f"these revisions are named as down_revision but do not exist: {orphan_parents}"
--
apps/api/tests\test_material_serialisation.py-106-    name the columns it must contain rather than trusting a reader to
apps/api/tests\test_material_serialisation.py-107-    remember. These are the NUMERIC columns of `materials.materials`
apps/api/tests\test_material_serialisation.py-108-    plus the supplier price that joins the row elsewhere.
apps/api/tests\test_material_serialisation.py-109-    """
apps/api/tests\test_material_serialisation.py:110:    expected = {
apps/api/tests\test_material_serialisation.py-111-        "density_g_cm3",
apps/api/tests\test_material_serialisation.py-112-        "solids_fraction",
apps/api/tests\test_material_serialisation.py-113-        "voc_fraction",
apps/api/tests\test_material_serialisation.py-114-        "cost_per_kg",
apps/api/tests\test_material_serialisation.py-115-        "epoxy_equivalent_weight",
apps/api/tests\test_material_serialisation.py-116-        "amine_hydrogen_equivalent_weight",
apps/api/tests\test_material_serialisation.py-117-        "quoted_price_per_kg",
apps/api/tests\test_material_serialisation.py-118-    }
apps/api/tests\test_material_serialisation.py:119:    assert set(_QUANTITY_KEYS) == expected, (
apps/api/tests\test_material_serialisation.py-120-        "the quantity list and this test disagree. If a NUMERIC column was "
apps/api/tests\test_material_serialisation.py-121-        "added, add it to BOTH; if one was removed, remove it from both."
apps/api/tests\test_material_serialisation.py-122-    )
--
apps/api/tests\test_keycloak_realm.py-69-        "Documentation belongs in services/keycloak/realm/README.md."
apps/api/tests\test_keycloak_realm.py-70-    )
apps/api/tests\test_keycloak_realm.py-71-
apps/api/tests\test_keycloak_realm.py-72-
apps/api/tests\test_keycloak_realm.py:73:def test_the_realm_is_the_one_the_application_expects() -> None:
apps/api/tests\test_keycloak_realm.py-74-    """The issuer path is built from this name.
apps/api/tests\test_keycloak_realm.py-75-
apps/api/tests\test_keycloak_realm.py-76-    `KEYCLOAK_ISSUER` ends in `/realms/evercoat`, and `verify_iss` is on.
apps/api/tests\test_keycloak_realm.py-77-    Renaming the realm would make every token fail issuer validation, and
--
apps/api/tests\test_keycloak_realm.py-130-            )
apps/api/tests\test_keycloak_realm.py-131-
apps/api/tests\test_keycloak_realm.py-132-
apps/api/tests\test_keycloak_realm.py-133-@pytest.mark.parametrize(
apps/api/tests\test_keycloak_realm.py:134:    "expected_role",
apps/api/tests\test_keycloak_realm.py-135-    [
apps/api/tests\test_keycloak_realm.py-136-        "product_development_chemist",
apps/api/tests\test_keycloak_realm.py-137-        "product_development_engineer",
apps/api/tests\test_keycloak_realm.py-138-        "product_development_lead",
--
apps/api/tests\test_keycloak_realm.py-144-        "executive_viewer",
apps/api/tests\test_keycloak_realm.py-145-        "administrator",
apps/api/tests\test_keycloak_realm.py-146-    ],
apps/api/tests\test_keycloak_realm.py-147-)
apps/api/tests\test_keycloak_realm.py:148:def test_every_role_the_bootstrap_assigns_exists_in_the_realm(expected_role: str) -> None:
apps/api/tests\test_keycloak_realm.py-149-    """`scripts/keycloak-bootstrap.sh` assigns one realm role per user.
apps/api/tests\test_keycloak_realm.py-150-
apps/api/tests\test_keycloak_realm.py-151-    A role named there but absent here fails at bootstrap time with a
apps/api/tests\test_keycloak_realm.py-152-    message about role mapping -- three steps from the cause. These are
apps/api/tests\test_keycloak_realm.py-153-    the same ten codes `test_002_roles_permissions.py` checks against
apps/api/tests\test_keycloak_realm.py-154-    `core.roles`, asserted from the other side.
apps/api/tests\test_keycloak_realm.py-155-    """
apps/api/tests\test_keycloak_realm.py-156-    roles = {r["name"] for r in _realm()["roles"]["realm"]}
apps/api/tests\test_keycloak_realm.py:157:    assert expected_role in roles, (
apps/api/tests\test_keycloak_realm.py:158:        f"the bootstrap script grants '{expected_role}' and the realm does not define it"
apps/api/tests\test_keycloak_realm.py-159-    )
apps/api/tests\test_keycloak_realm.py-160-
apps/api/tests\test_keycloak_realm.py-161-
apps/api/tests\test_keycloak_realm.py-162-# ---------------------------------------------------------------------
--
apps/api/tests\test_keycloak_realm.py-194-
apps/api/tests\test_keycloak_realm.py-195-
apps/api/tests\test_keycloak_realm.py-196-def test_every_redirect_uri_uses_the_path_the_application_actually_serves() -> None:
apps/api/tests\test_keycloak_realm.py-197-    """The realm's callback path must equal `CALLBACK_PATH` in the web app."""
apps/api/tests\test_keycloak_realm.py:198:    expected = _callback_path_from_web()
apps/api/tests\test_keycloak_realm.py-199-    redirect_uris = _web_client().get("redirectUris", [])
apps/api/tests\test_keycloak_realm.py-200-    assert redirect_uris, "evercoat-web has no redirectUris, so sign-in cannot complete"
apps/api/tests\test_keycloak_realm.py-201-
apps/api/tests\test_keycloak_realm.py:202:    wrong = [uri for uri in redirect_uris if not uri.endswith(expected)]
apps/api/tests\test_keycloak_realm.py-203-    assert not wrong, (
apps/api/tests\test_keycloak_realm.py-204-        f"these redirect URIs do not end with the application's CALLBACK_PATH "
apps/api/tests\test_keycloak_realm.py:205:        f"({expected!r}). Keycloak refuses a mismatch with invalid_redirect_uri "
apps/api/tests\test_keycloak_realm.py-206-        f"before issuing a code, so there is nothing in any log to diagnose:\n  "
apps/api/tests\test_keycloak_realm.py-207-        + "\n  ".join(wrong)
apps/api/tests\test_keycloak_realm.py-208-    )
apps/api/tests\test_keycloak_realm.py-209-
apps/api/tests\test_keycloak_realm.py-210-
apps/api/tests\test_keycloak_realm.py-211-def test_the_realm_no_longer_points_at_next_auth() -> None:
apps/api/tests\test_keycloak_realm.py:212:    """ADR-025: next-auth cannot run in a static export and was removed.
apps/api/tests\test_keycloak_realm.py-213-
apps/api/tests\test_keycloak_realm.py-214-    A leftover `/api/auth/callback/keycloak` entry would be a redirect URI
apps/api/tests\test_keycloak_realm.py-215-    the application can never serve -- and, being valid-looking, exactly
apps/api/tests\test_keycloak_realm.py-216-    the kind of thing that gets copied forward.
--
apps/api/tests\test_keycloak_realm.py-218-    redirect_uris = _web_client().get("redirectUris", [])
apps/api/tests\test_keycloak_realm.py-219-    stale = [uri for uri in redirect_uris if "/api/auth/" in uri]
apps/api/tests\test_keycloak_realm.py-220-    assert not stale, (
apps/api/tests\test_keycloak_realm.py-221-        "these redirect URIs still point at next-auth route handlers, which a "
apps/api/tests\test_keycloak_realm.py:222:        "static export does not have (ADR-025):\n  " + "\n  ".join(stale)
apps/api/tests\test_keycloak_realm.py-223-    )
apps/api/tests\test_keycloak_realm.py-224-
apps/api/tests\test_keycloak_realm.py-225-
apps/api/tests\test_keycloak_realm.py-226-def test_the_web_client_can_still_do_pkce() -> None:
--
apps/api/tests\test_bootstrap_scripts.py-2-
apps/api/tests\test_bootstrap_scripts.py-3-🔴 WHAT THIS CATCHES
apps/api/tests\test_bootstrap_scripts.py-4-
apps/api/tests\test_bootstrap_scripts.py-5-Two CI runs of the `auth` job died with a bare `Process completed with
apps/api/tests\test_bootstrap_scripts.py:6:exit code 6` -- curl's "could not resolve host" -- immediately after a
apps/api/tests\test_bootstrap_scripts.py-7-user had been created successfully, and printed nothing else. Reasoning
apps/api/tests\test_bootstrap_scripts.py-8-from the source was wrong twice. `bash -x` on the step gave the answer in
apps/api/tests\test_bootstrap_scripts.py-9-one line:
apps/api/tests\test_bootstrap_scripts.py-10-
--
apps/api/tests\test_bootstrap_scripts.py-22-
apps/api/tests\test_bootstrap_scripts.py-23-2. `-w '%{http_code}'` prints ONCE PER URL. Two URLs therefore produced
apps/api/tests\test_bootstrap_scripts.py-24-   the single string `204000`, which is not a status at all.
apps/api/tests\test_bootstrap_scripts.py-25-
apps/api/tests\test_bootstrap_scripts.py:26:3. `expect_status` matched with `case "$got" in 2*)`, so `204000` would
apps/api/tests\test_bootstrap_scripts.py-27-   have been accepted as success. Only curl's exit code stopped the run.
apps/api/tests\test_bootstrap_scripts.py-28-   Had the stray second URL happened to resolve, a **failed role mapping
apps/api/tests\test_bootstrap_scripts.py-29-   would have passed the gate silently** -- and the failure would have
apps/api/tests\test_bootstrap_scripts.py-30-   surfaced four steps later as `invalid_grant`, reading as a wrong
--
apps/api/tests\test_bootstrap_scripts.py-160-def test_the_curl_error_file_is_not_a_predictable_shared_path() -> None:
apps/api/tests\test_bootstrap_scripts.py-161-    """A fixed name in /tmp is another user's symlink and another run's file."""
apps/api/tests\test_bootstrap_scripts.py-162-    source = BOOTSTRAP.read_text(encoding="utf-8")
apps/api/tests\test_bootstrap_scripts.py-163-    # Comments are excluded on purpose: the script's own commentary names
apps/api/tests\test_bootstrap_scripts.py:164:    # the old path to explain why it went.
apps/api/tests\test_bootstrap_scripts.py-165-    code_lines = [line for line in source.splitlines() if not line.lstrip().startswith("#")]
apps/api/tests\test_bootstrap_scripts.py-166-    # S108 is suppressed below: this names the bad path in order to FORBID
apps/api/tests\test_bootstrap_scripts.py-167-    # it, and is the one place the literal must appear.
apps/api/tests\test_bootstrap_scripts.py-168-    offenders = [line.strip() for line in code_lines if "/tmp/kc-curl-err" in line]  # noqa: S108
--
apps/api/tests\test_bootstrap_scripts.py-210-        ("", False),
apps/api/tests\test_bootstrap_scripts.py-211-        ("20", False),
apps/api/tests\test_bootstrap_scripts.py-212-    ],
apps/api/tests\test_bootstrap_scripts.py-213-)
apps/api/tests\test_bootstrap_scripts.py:214:def test_expect_status_accepts_only_a_three_digit_status(status: str, should_pass: bool) -> None:
apps/api/tests\test_bootstrap_scripts.py-215-    """`204000` must be refused. `case "$got" in 2*)` used to accept it."""
apps/api/tests\test_bootstrap_scripts.py-216-    if BASH is None:
apps/api/tests\test_bootstrap_scripts.py-217-        pytest.skip("bash is not available on this host")
apps/api/tests\test_bootstrap_scripts.py:218:    body = _extract_function("expect_status", BOOTSTRAP.read_text(encoding="utf-8"))
apps/api/tests\test_bootstrap_scripts.py:219:    program = f'{body}\nexpect_status "$1" "a test call"\necho ACCEPTED\n'
apps/api/tests\test_bootstrap_scripts.py-220-    result = subprocess.run(  # noqa: S603 -- BASH is from shutil.which; the program is built above
apps/api/tests\test_bootstrap_scripts.py-221-        [BASH, "-c", program, "bash", status],
apps/api/tests\test_bootstrap_scripts.py-222-        capture_output=True,
apps/api/tests\test_bootstrap_scripts.py-223-        text=True,
apps/api/tests\test_bootstrap_scripts.py-224-        timeout=30,
apps/api/tests\test_bootstrap_scripts.py-225-    )
apps/api/tests\test_bootstrap_scripts.py-226-    accepted = result.returncode == 0 and "ACCEPTED" in result.stdout
apps/api/tests\test_bootstrap_scripts.py-227-    assert accepted is should_pass, (
apps/api/tests\test_bootstrap_scripts.py:228:        f"expect_status({status!r}) "
apps/api/tests\test_bootstrap_scripts.py-229-        f"{'was rejected' if should_pass else 'was ACCEPTED'} "
apps/api/tests\test_bootstrap_scripts.py-230-        f"-- rc={result.returncode} stdout={result.stdout!r} "
apps/api/tests\test_bootstrap_scripts.py-231-        f"stderr={result.stderr!r}"
apps/api/tests\test_bootstrap_scripts.py-232-    )
--
apps/api/tests\integration\test_auth_end_to_end.py-1-"""Authentication against a REAL Keycloak, end to end.
apps/api/tests\integration\test_auth_end_to_end.py-2-
apps/api/tests\integration\test_auth_end_to_end.py-3-🔴 WHAT HAS NEVER BEEN PROVEN UNTIL THIS FILE
apps/api/tests\integration\test_auth_end_to_end.py-4-
apps/api/tests\integration\test_auth_end_to_end.py:5:`app/core/security.py` verifies signature, issuer, audience and expiry,
apps/api/tests\integration\test_auth_end_to_end.py-6-then resolves a principal from the database. Every one of those steps has
apps/api/tests\integration\test_auth_end_to_end.py-7-been unit-tested with a fabricated token or mocked out entirely. None of
apps/api/tests\integration\test_auth_end_to_end.py-8-them had ever run against a token an actual identity provider minted,
apps/api/tests\integration\test_auth_end_to_end.py-9-because no Keycloak had ever run anywhere -- not on Render, not in CI,
--
apps/api/tests\integration\test_auth_end_to_end.py-108-
apps/api/tests\integration\test_auth_end_to_end.py-109-def test_a_real_token_resolves_to_a_principal() -> None:
apps/api/tests\integration\test_auth_end_to_end.py-110-    """The whole chain, in one assertion.
apps/api/tests\integration\test_auth_end_to_end.py-111-
apps/api/tests\integration\test_auth_end_to_end.py:112:    Keycloak mints it, the API verifies the signature against JWKS
apps/api/tests\integration\test_auth_end_to_end.py-113-    fetched over the network, checks issuer and audience, then finds the
apps/api/tests\integration\test_auth_end_to_end.py-114-    matching `core.users` row by `keycloak_sub` and reads that user's
apps/api/tests\integration\test_auth_end_to_end.py-115-    real roles and permissions out of the database.
apps/api/tests\integration\test_auth_end_to_end.py-116-
--
apps/api/tests\integration\test_auth_end_to_end.py-269-    A route that returns a plausible organization id which `get_principal`
apps/api/tests\integration\test_auth_end_to_end.py-270-    then rejects would be worse than no route at all -- it would look
apps/api/tests\integration\test_auth_end_to_end.py-271-    correct and fail one step later, which is the shape of defect this
apps/api/tests\integration\test_auth_end_to_end.py-272-    project keeps catching. So the id is taken from `/api/me` and spent
apps/api/tests\integration\test_auth_end_to_end.py:273:    immediately on a route that enforces membership.
apps/api/tests\integration\test_auth_end_to_end.py-274-    """
apps/api/tests\integration\test_auth_end_to_end.py-275-    token = _token("lead.demo")
apps/api/tests\integration\test_auth_end_to_end.py-276-    me = httpx.get(
apps/api/tests\integration\test_auth_end_to_end.py-277-        f"{API_URL}/api/me",
--
apps/api/tests\db\test_001_core_tenancy.py-1-"""Tenancy and audit invariants.
apps/api/tests\db\test_001_core_tenancy.py-2-
apps/api/tests\db\test_001_core_tenancy.py-3-These are the gate for the riskiest decision in the project. Both
apps/api/tests\db\test_001_core_tenancy.py-4-reviewers named the authorization and tenancy model as the thing most
apps/api/tests\db\test_001_core_tenancy.py:5:likely to force an expensive rewrite if it is wrong (Codex Q3), so it
apps/api/tests\db\test_001_core_tenancy.py-6-gets asserted rather than assumed.
apps/api/tests\db\test_001_core_tenancy.py-7-
apps/api/tests\db\test_001_core_tenancy.py-8-Every test here runs under ``SET ROLE evercoat_app``. A migration or a
apps/api/tests\db\test_001_core_tenancy.py-9-query that only works as superuser is a latent production failure:
--
apps/api/tests\db\test_001_core_tenancy.py-264-    # INVOKER and filtered by audit_org_isolation, so every writer chained
apps/api/tests\db\test_001_core_tenancy.py-265-    # onto its own organization's tail. Two organizations therefore both
apps/api/tests\db\test_001_core_tenancy.py-266-    # started at GENESIS -- the observed symptom -- for a reason that had
apps/api/tests\db\test_001_core_tenancy.py-267-    # nothing to do with concurrency. Migration 011 makes the per-
apps/api/tests\db\test_001_core_tenancy.py:268:    # organization scope explicit and stops unscoped writers splicing
apps/api/tests\db\test_001_core_tenancy.py-269-    # across tenants.
apps/api/tests\db\test_001_core_tenancy.py-270-    #
apps/api/tests\db\test_001_core_tenancy.py-271-    # The fixture writes rows with no organization_id, so these belong to
apps/api/tests\db\test_001_core_tenancy.py-272-    # the SYSTEM chain and organization_id=None is what selects them.
--
apps/api/tests\db\test_001_core_tenancy.py-285-
apps/api/tests\db\test_001_core_tenancy.py-286-    break_found = verify_chain(owner_session, organization_id=None, start_id=start)
apps/api/tests\db\test_001_core_tenancy.py-287-    assert break_found is not None, "tampering went undetected"
apps/api/tests\db\test_001_core_tenancy.py-288-    assert break_found.event_id == target, (
apps/api/tests\db\test_001_core_tenancy.py:289:        f"expected the break at the altered row {target}, got {break_found.event_id}"
apps/api/tests\db\test_001_core_tenancy.py-290-    )
apps/api/tests\db\test_001_core_tenancy.py-291-
apps/api/tests\db\test_001_core_tenancy.py-292-
apps/api/tests\db\test_001_core_tenancy.py-293-def test_python_and_sql_agree_on_the_hash(owner_session, one_audit_row):
--
apps/api/tests\db\conftest.py-130-@pytest.fixture
apps/api/tests\db\conftest.py-131-def seeded_projects(owner_session) -> Iterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]]:
apps/api/tests\db\conftest.py-132-    """One organization, a normal project, a restricted project, a non-member.
apps/api/tests\db\conftest.py-133-
apps/api/tests\db\conftest.py:134:    This fixture COMMITS, unlike the others, and cleans up explicitly.
apps/api/tests\db\conftest.py-135-
apps/api/tests\db\conftest.py-136-    It has to. The visibility tests read through ``app_session``, which is
apps/api/tests\db\conftest.py-137-    a different connection — so uncommitted rows written by
apps/api/tests\db\conftest.py-138-    ``owner_session`` are invisible to it, and the test fails claiming RLS
--
apps/api/tests\db\test_017_laboratory.py-340-) -> None:
apps/api/tests\db\test_017_laboratory.py-341-    """An instruction that was issued cannot be rewritten afterwards.
apps/api/tests\db\test_017_laboratory.py-342-
apps/api/tests\db\test_017_laboratory.py-343-    Otherwise a line weighed 200 g heavy could be "corrected" by moving
apps/api/tests\db\test_017_laboratory.py:344:    the plan, and the reconciliation would show a perfect batch.
apps/api/tests\db\test_017_laboratory.py-345-    """
apps/api/tests\db\test_017_laboratory.py-346-    fx = approved_formula
apps/api/tests\db\test_017_laboratory.py-347-    batch_id = _create(owner_session, fx)
apps/api/tests\db\test_017_laboratory.py-348-    authorize_batch(
--
apps/api/tests\db\test_017_laboratory.py-519-
apps/api/tests\db\test_017_laboratory.py-520-def test_a_rejected_batch_must_say_what_went_wrong(
apps/api/tests\db\test_017_laboratory.py-521-    owner_session: Session, approved_formula: dict[str, uuid.UUID]
apps/api/tests\db\test_017_laboratory.py-522-) -> None:
apps/api/tests\db\test_017_laboratory.py:523:    """ "Rejected" with no stated deviation is a verdict nobody can learn
apps/api/tests\db\test_017_laboratory.py-524-    from, and the next person to make this formula needs to know."""
apps/api/tests\db\test_017_laboratory.py-525-    fx = approved_formula
apps/api/tests\db\test_017_laboratory.py-526-    batch_id = _create(owner_session, fx)
apps/api/tests\db\test_017_laboratory.py-527-    authorize_batch(
--
apps/api/tests\db\test_017_laboratory.py-534-    complete_batch(
apps/api/tests\db\test_017_laboratory.py-535-        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
apps/api/tests\db\test_017_laboratory.py-536-    )
apps/api/tests\db\test_017_laboratory.py-537-
apps/api/tests\db\test_017_laboratory.py:538:    with pytest.raises(Exception, match="deviation"):
apps/api/tests\db\test_017_laboratory.py-539-        review_batch(
apps/api/tests\db\test_017_laboratory.py-540-            owner_session,
apps/api/tests\db\test_017_laboratory.py-541-            batch_id=batch_id,
apps/api/tests\db\test_017_laboratory.py-542-            organization_id=fx["org"],
--
apps/api/tests\db\test_017_laboratory.py-584-# Reading
apps/api/tests\db\test_017_laboratory.py-585-# ---------------------------------------------------------------------------
apps/api/tests\db\test_017_laboratory.py-586-
apps/api/tests\db\test_017_laboratory.py-587-
apps/api/tests\db\test_017_laboratory.py:588:def test_an_unweighed_line_reports_no_deviation_rather_than_zero(
apps/api/tests\db\test_017_laboratory.py-589-    owner_session: Session, approved_formula: dict[str, uuid.UUID]
apps/api/tests\db\test_017_laboratory.py-590-) -> None:
apps/api/tests\db\test_017_laboratory.py-591-    """🔴 ABSENCE MUST NOT PRESENT AS SUCCESS.
apps/api/tests\db\test_017_laboratory.py-592-
--
apps/api/tests\db\test_017_laboratory.py-600-
apps/api/tests\db\test_017_laboratory.py-601-    assert len(batch["components"]) == 2
apps/api/tests\db\test_017_laboratory.py-602-    for line in batch["components"]:
apps/api/tests\db\test_017_laboratory.py-603-        assert line["actual_mass_kg"] is None
apps/api/tests\db\test_017_laboratory.py:604:        assert line["deviation"] is None
apps/api/tests\db\test_017_laboratory.py-605-
apps/api/tests\db\test_017_laboratory.py-606-
apps/api/tests\db\test_017_laboratory.py:607:def test_a_weighed_line_carries_its_deviation(
apps/api/tests\db\test_017_laboratory.py-608-    owner_session: Session, approved_formula: dict[str, uuid.UUID]
apps/api/tests\db\test_017_laboratory.py-609-) -> None:
apps/api/tests\db\test_017_laboratory.py-610-    """Derived at read time, never stored.
apps/api/tests\db\test_017_laboratory.py-611-
--
apps/api/tests\db\test_015_materials_formulations.py-512-    owner_session: Session, approved_version: tuple[uuid.UUID, ...]
apps/api/tests\db\test_015_materials_formulations.py-513-) -> None:
apps/api/tests\db\test_015_materials_formulations.py-514-    """The one field section 8 requires to keep moving after freezing.
apps/api/tests\db\test_015_materials_formulations.py-515-
apps/api/tests\db\test_015_materials_formulations.py:516:    Every version records an expected effect and, AFTER TESTING, an
apps/api/tests\db\test_015_materials_formulations.py-517-    observed one. A trigger that froze this column too would make the
apps/api/tests\db\test_015_materials_formulations.py-518-    digital thread one-way: the hypothesis preserved forever and the
apps/api/tests\db\test_015_materials_formulations.py-519-    answer to it impossible to record.
apps/api/tests\db\test_015_materials_formulations.py-520-    """
--
apps/api/tests\db\test_015_materials_formulations.py-565-
apps/api/tests\db\test_015_materials_formulations.py-566-def test_two_children_of_one_parent_is_a_branch_and_is_permitted(
apps/api/tests\db\test_015_materials_formulations.py-567-    owner_session: Session, actor: uuid.UUID
apps/api/tests\db\test_015_materials_formulations.py-568-) -> None:
apps/api/tests\db\test_015_materials_formulations.py:569:    """F004-A / F004-B. The plan requires branches to be expressible.
apps/api/tests\db\test_015_materials_formulations.py-570-
apps/api/tests\db\test_015_materials_formulations.py-571-    A constraint that allowed only one revision per version would make a
apps/api/tests\db\test_015_materials_formulations.py-572-    branch impossible, and would do it silently -- the second chemist
apps/api/tests\db\test_015_materials_formulations.py-573-    would see a unique-violation about version numbers and conclude the
--
apps/api/tests\db\test_015_materials_formulations.py-643-                "a": actor,
apps/api/tests\db\test_015_materials_formulations.py-644-            },
apps/api/tests\db\test_015_materials_formulations.py-645-        )
apps/api/tests\db\test_015_materials_formulations.py-646-
apps/api/tests\db\test_015_materials_formulations.py:647:    assert "formula_versions_revision_is_explained" in str(caught.value.orig)
apps/api/tests\db\test_015_materials_formulations.py-648-
apps/api/tests\db\test_015_materials_formulations.py-649-
apps/api/tests\db\test_015_materials_formulations.py-650-def test_an_approved_version_must_name_its_approver(
apps/api/tests\db\test_015_materials_formulations.py-651-    owner_session: Session, actor: uuid.UUID
--
apps/api/tests\calculations\test_traffic_light.py-8-is RED either way, and only the LABEL and the rule number reveal which
apps/api/tests\calculations\test_traffic_light.py-9-rule decided. So every ordering test asserts `disposition.rule`.
apps/api/tests\calculations\test_traffic_light.py-10-
apps/api/tests\calculations\test_traffic_light.py-11-That is also why `Disposition` carries the rule number at all. A traffic
apps/api/tests\calculations\test_traffic_light.py:12:light nobody can explain is a traffic light nobody trusts.
apps/api/tests\calculations\test_traffic_light.py-13-"""
apps/api/tests\calculations\test_traffic_light.py-14-
apps/api/tests\calculations\test_traffic_light.py-15-from __future__ import annotations
apps/api/tests\calculations\test_traffic_light.py-16-
--
apps/api/tests\calculations\test_traffic_light.py-132-    assert d.rule == 5
apps/api/tests\calculations\test_traffic_light.py-133-    assert "2 valid replicate(s) of 3" in d.reason
apps/api/tests\calculations\test_traffic_light.py-134-
apps/api/tests\calculations\test_traffic_light.py-135-
apps/api/tests\calculations\test_traffic_light.py:136:def test_a_returned_review_beats_a_recorded_deviation() -> None:
apps/api/tests\calculations\test_traffic_light.py-137-    """Rule 7 before 8. Both are yellow; the actionable one is the review
apps/api/tests\calculations\test_traffic_light.py-138-    state, because somebody is waiting on the submitter."""
apps/api/tests\calculations\test_traffic_light.py-139-    d = derive_disposition(
apps/api/tests\calculations\test_traffic_light.py:140:        passing_state(review_state="returned_for_correction", validity_status="minor_deviation")
apps/api/tests\calculations\test_traffic_light.py-141-    )
apps/api/tests\calculations\test_traffic_light.py-142-    assert d.rule == 7
apps/api/tests\calculations\test_traffic_light.py-143-    assert d.next_action == "correct and resubmit the result"
apps/api/tests\calculations\test_traffic_light.py-144-
--
apps/api/tests\calculations\test_traffic_light.py-215-
apps/api/tests\calculations\test_traffic_light.py-216-    GREEN is authority-qualified — never a bare tick. Somebody reading
apps/api/tests\calculations\test_traffic_light.py-217-    only the colour would otherwise treat a screening pass as
apps/api/tests\calculations\test_traffic_light.py-218-    qualification evidence, which is exactly what X12 in the plan's
apps/api/tests\calculations\test_traffic_light.py:219:    reconciliation register exists to prevent.
apps/api/tests\calculations\test_traffic_light.py-220-    """
apps/api/tests\calculations\test_traffic_light.py-221-    d = derive_disposition(passing_state(test_purpose="screening", final_confirmed=False))
apps/api/tests\calculations\test_traffic_light.py-222-
apps/api/tests\calculations\test_traffic_light.py-223-    assert d.colour == "green"
--
apps/api/tests\calculations\test_traffic_light.py-239-# ---------------------------------------------------------------------------
apps/api/tests\calculations\test_traffic_light.py-240-
apps/api/tests\calculations\test_traffic_light.py-241-
apps/api/tests\calculations\test_traffic_light.py-242-def test_every_yellow_states_why_and_what_happens_next() -> None:
apps/api/tests\calculations\test_traffic_light.py:243:    """§3.3: "A yellow with no explanation is a defect."
apps/api/tests\calculations\test_traffic_light.py-244-
apps/api/tests\calculations\test_traffic_light.py-245-    Exhaustive over every yellow-producing state this module can reach,
apps/api/tests\calculations\test_traffic_light.py-246-    so a rule added later without a next action fails here rather than
apps/api/tests\calculations\test_traffic_light.py-247-    reaching a screen.
--
apps/api/tests\calculations\test_traffic_light.py-252-        passing_state(cv_percent=Decimal("40"), cv_limit=Decimal("5")),
apps/api/tests\calculations\test_traffic_light.py-253-        passing_state(review_state="returned_for_correction"),
apps/api/tests\calculations\test_traffic_light.py-254-        passing_state(review_state="retest_requested"),
apps/api/tests\calculations\test_traffic_light.py-255-        passing_state(review_state="escalated"),
apps/api/tests\calculations\test_traffic_light.py:256:        passing_state(validity_status="minor_deviation"),
apps/api/tests\calculations\test_traffic_light.py-257-        passing_state(margin_percent=Decimal("1"), warning_threshold=Decimal("10")),
apps/api/tests\calculations\test_traffic_light.py-258-        passing_state(trend_alert=True),
apps/api/tests\calculations\test_traffic_light.py-259-        passing_state(approval_state="conditionally_approved", approval_condition="limited"),
apps/api/tests\calculations\test_traffic_light.py-260-        passing_state(approval_state="pending"),
apps/api/tests\calculations\test_traffic_light.py-261-    ]
apps/api/tests\calculations\test_traffic_light.py-262-
apps/api/tests\calculations\test_traffic_light.py-263-    for state in yellow_states:
apps/api/tests\calculations\test_traffic_light.py-264-        d = derive_disposition(state)
apps/api/tests\calculations\test_traffic_light.py:265:        assert d.colour == "yellow", f"expected yellow, got {d.colour} from rule {d.rule}"
apps/api/tests\calculations\test_traffic_light.py-266-        assert d.reason, f"rule {d.rule} produced a yellow with no reason"
apps/api/tests\calculations\test_traffic_light.py-267-        assert d.next_action, f"rule {d.rule} produced a yellow with no next action"
apps/api/tests\calculations\test_traffic_light.py-268-
apps/api/tests\calculations\test_traffic_light.py-269-
--
apps/api/tests\calculations\test_traffic_light.py-306-# Replicate statistics
apps/api/tests\calculations\test_traffic_light.py-307-# ---------------------------------------------------------------------------
apps/api/tests\calculations\test_traffic_light.py-308-
apps/api/tests\calculations\test_traffic_light.py-309-
apps/api/tests\calculations\test_traffic_light.py:310:def test_a_single_replicate_has_no_standard_deviation() -> None:
apps/api/tests\calculations\test_traffic_light.py-311-    """`None`, not zero.
apps/api/tests\calculations\test_traffic_light.py-312-
apps/api/tests\calculations\test_traffic_light.py-313-    Zero says "perfectly repeatable", which one measurement cannot
apps/api/tests\calculations\test_traffic_light.py-314-    support — and because rule 6 compares CV against a limit, a spurious
apps/api/tests\calculations\test_traffic_light.py-315-    0.0 would silently pass every single-replicate test.
apps/api/tests\calculations\test_traffic_light.py-316-    """
apps/api/tests\calculations\test_traffic_light.py-317-    stats = replicate_statistics([Decimal("5.30")])
apps/api/tests\calculations\test_traffic_light.py-318-    assert stats.mean == Decimal("5.30")
apps/api/tests\calculations\test_traffic_light.py:319:    assert stats.standard_deviation is None
apps/api/tests\calculations\test_traffic_light.py-320-    assert stats.cv_percent is None
apps/api/tests\calculations\test_traffic_light.py-321-
apps/api/tests\calculations\test_traffic_light.py-322-
apps/api/tests\calculations\test_traffic_light.py:323:def test_the_standard_deviation_is_the_sample_form_not_the_population_form() -> None:
apps/api/tests\calculations\test_traffic_light.py-324-    """n-1, not n.
apps/api/tests\calculations\test_traffic_light.py-325-
apps/api/tests\calculations\test_traffic_light.py-326-    Replicates are a sample of the measurement process, not the whole of
apps/api/tests\calculations\test_traffic_light.py-327-    it. The population form understates variability, which would make
--
apps/api/tests\calculations\test_traffic_light.py-334-    values = [Decimal(n) for n in (2, 4, 4, 4, 5, 5, 7, 9)]
apps/api/tests\calculations\test_traffic_light.py-335-    stats = replicate_statistics(values)
apps/api/tests\calculations\test_traffic_light.py-336-
apps/api/tests\calculations\test_traffic_light.py-337-    assert stats.mean == Decimal("5")
apps/api/tests\calculations\test_traffic_light.py:338:    assert stats.standard_deviation is not None
apps/api/tests\calculations\test_traffic_light.py:339:    assert stats.standard_deviation > Decimal("2.1")
apps/api/tests\calculations\test_traffic_light.py:340:    assert stats.standard_deviation < Decimal("2.2")
apps/api/tests\calculations\test_traffic_light.py-341-
apps/api/tests\calculations\test_traffic_light.py-342-
apps/api/tests\calculations\test_traffic_light.py-343-def test_no_replicates_is_not_a_mean_of_zero() -> None:
apps/api/tests\calculations\test_traffic_light.py-344-    """An empty set has no mean. Reporting 0 would put a fabricated
--
apps/api/tests\calculations\test_traffic_light.py-386-    assert result.margin_percent < Decimal("2")
apps/api/tests\calculations\test_traffic_light.py-387-
apps/api/tests\calculations\test_traffic_light.py-388-
apps/api/tests\calculations\test_traffic_light.py-389-@pytest.mark.parametrize(
apps/api/tests\calculations\test_traffic_light.py:390:    ("value", "expected"),
apps/api/tests\calculations\test_traffic_light.py-391-    [("4.9", "fail"), ("5.0", "pass"), ("9.0", "pass"), ("10.0", "pass"), ("10.1", "fail")],
apps/api/tests\calculations\test_traffic_light.py-392-)
apps/api/tests\calculations\test_traffic_light.py:393:def test_the_bounds_are_inclusive(value: str, expected: str) -> None:
apps/api/tests\calculations\test_traffic_light.py-394-    """A requirement of "at least 5.0" is met BY 5.0.
apps/api/tests\calculations\test_traffic_light.py-395-
apps/api/tests\calculations\test_traffic_light.py-396-    An exclusive comparison fails a result that exactly meets the
apps/api/tests\calculations\test_traffic_light.py-397-    specification, which is both wrong and the kind of off-by-one nobody
--
apps/api/tests\calculations\test_traffic_light.py-399-    """
apps/api/tests\calculations\test_traffic_light.py-400-    result = evaluate_against_requirement(
apps/api/tests\calculations\test_traffic_light.py-401-        Decimal(value), minimum=Decimal("5.0"), maximum=Decimal("10.0")
apps/api/tests\calculations\test_traffic_light.py-402-    )
apps/api/tests\calculations\test_traffic_light.py:403:    assert result.result == expected
apps/api/tests\calculations\test_traffic_light.py-404-
apps/api/tests\calculations\test_traffic_light.py-405-
apps/api/tests\calculations\test_traffic_light.py-406-def test_an_impossible_requirement_is_refused_rather_than_silently_failing() -> None:
apps/api/tests\calculations\test_traffic_light.py-407-    """min above max grades every measurement as a failure, which looks
--
apps/api/tests\calculations\test_mass_deviation.py:1:"""`mass_deviation` — the weighing reconciliation.
apps/api/tests\calculations\test_mass_deviation.py-2-
apps/api/tests\calculations\test_mass_deviation.py-3-Property-based where the property is the point, example-based where a
apps/api/tests\calculations\test_mass_deviation.py-4-specific number carries the meaning. `CLAUDE.md` §15 requires Hypothesis
apps/api/tests\calculations\test_mass_deviation.py:5:for scientific code, and a reconciliation a technician acts on at the
apps/api/tests\calculations\test_mass_deviation.py-6-bench qualifies.
apps/api/tests\calculations\test_mass_deviation.py-7-"""
apps/api/tests\calculations\test_mass_deviation.py-8-
apps/api/tests\calculations\test_mass_deviation.py-9-from __future__ import annotations
--
apps/api/tests\calculations\test_mass_deviation.py-13-import pytest
apps/api/tests\calculations\test_mass_deviation.py-14-from hypothesis import given
apps/api/tests\calculations\test_mass_deviation.py-15-from hypothesis import strategies as st
apps/api/tests\calculations\test_mass_deviation.py-16-
apps/api/tests\calculations\test_mass_deviation.py:17:from app.calculations.formulation import mass_deviation
apps/api/tests\calculations\test_mass_deviation.py-18-
apps/api/tests\calculations\test_mass_deviation.py-19-# Realistic bench masses: a gram to a hundred kilograms, to the milligram.
apps/api/tests\calculations\test_mass_deviation.py-20-masses = st.decimals(
apps/api/tests\calculations\test_mass_deviation.py-21-    min_value=Decimal("0.001"),
--
apps/api/tests\calculations\test_mass_deviation.py-34-    would make every minor component look perfect — and minor components
apps/api/tests\calculations\test_mass_deviation.py-35-    are catalysts and hardeners, where a proportional error does the most
apps/api/tests\calculations\test_mass_deviation.py-36-    damage.
apps/api/tests\calculations\test_mass_deviation.py-37-    """
apps/api/tests\calculations\test_mass_deviation.py:38:    small = mass_deviation(Decimal("0.010"), Decimal("0.015"))
apps/api/tests\calculations\test_mass_deviation.py:39:    large = mass_deviation(Decimal("20.000"), Decimal("20.005"))
apps/api/tests\calculations\test_mass_deviation.py-40-
apps/api/tests\calculations\test_mass_deviation.py-41-    assert small.delta_percent == Decimal("50")
apps/api/tests\calculations\test_mass_deviation.py-42-    assert small.within_tolerance is False
apps/api/tests\calculations\test_mass_deviation.py-43-
--
apps/api/tests\calculations\test_mass_deviation.py-50-
apps/api/tests\calculations\test_mass_deviation.py-51-    Too much hardener and too little hardener are different faults with
apps/api/tests\calculations\test_mass_deviation.py-52-    different consequences; reporting a magnitude would collapse them.
apps/api/tests\calculations\test_mass_deviation.py-53-    """
apps/api/tests\calculations\test_mass_deviation.py:54:    over = mass_deviation(Decimal("10.000"), Decimal("10.500"))
apps/api/tests\calculations\test_mass_deviation.py:55:    under = mass_deviation(Decimal("10.000"), Decimal("9.500"))
apps/api/tests\calculations\test_mass_deviation.py-56-
apps/api/tests\calculations\test_mass_deviation.py-57-    assert over.delta_kg > 0
apps/api/tests\calculations\test_mass_deviation.py-58-    assert under.delta_kg < 0
apps/api/tests\calculations\test_mass_deviation.py-59-    assert over.delta_percent == -under.delta_percent
--
apps/api/tests\calculations\test_mass_deviation.py-65-    A naive `percent <= tolerance` passes every under-charge, however
apps/api/tests\calculations\test_mass_deviation.py-66-    large, because a negative number is always below the limit. That bug
apps/api/tests\calculations\test_mass_deviation.py-67-    would be invisible in any test that only weighs too much.
apps/api/tests\calculations\test_mass_deviation.py-68-    """
apps/api/tests\calculations\test_mass_deviation.py:69:    over = mass_deviation(Decimal("10.0"), Decimal("10.4"), tolerance_percent=Decimal("3"))
apps/api/tests\calculations\test_mass_deviation.py:70:    under = mass_deviation(Decimal("10.0"), Decimal("9.6"), tolerance_percent=Decimal("3"))
apps/api/tests\calculations\test_mass_deviation.py-71-
apps/api/tests\calculations\test_mass_deviation.py-72-    assert over.within_tolerance is False
apps/api/tests\calculations\test_mass_deviation.py-73-    assert under.within_tolerance is False
apps/api/tests\calculations\test_mass_deviation.py-74-
apps/api/tests\calculations\test_mass_deviation.py-75-
apps/api/tests\calculations\test_mass_deviation.py-76-def test_a_planned_mass_of_zero_is_refused() -> None:
apps/api/tests\calculations\test_mass_deviation.py:77:    """Not reported as an infinite deviation.
apps/api/tests\calculations\test_mass_deviation.py-78-
apps/api/tests\calculations\test_mass_deviation.py-79-    A component planned at zero is not a component, and the weigh-up
apps/api/tests\calculations\test_mass_deviation.py-80-    sheet should never have produced the line. Returning infinity would
apps/api/tests\calculations\test_mass_deviation.py-81-    push a meaningless figure onto a screen; raising says where the fault
apps/api/tests\calculations\test_mass_deviation.py-82-    actually is.
apps/api/tests\calculations\test_mass_deviation.py-83-    """
apps/api/tests\calculations\test_mass_deviation.py-84-    with pytest.raises(ValueError, match="positive"):
apps/api/tests\calculations\test_mass_deviation.py:85:        mass_deviation(Decimal("0"), Decimal("1.0"))
apps/api/tests\calculations\test_mass_deviation.py-86-
apps/api/tests\calculations\test_mass_deviation.py-87-
apps/api/tests\calculations\test_mass_deviation.py-88-def test_a_negative_weight_is_refused() -> None:
apps/api/tests\calculations\test_mass_deviation.py-89-    with pytest.raises(ValueError, match="negative"):
apps/api/tests\calculations\test_mass_deviation.py:90:        mass_deviation(Decimal("1.0"), Decimal("-0.5"))
apps/api/tests\calculations\test_mass_deviation.py-91-
apps/api/tests\calculations\test_mass_deviation.py-92-
apps/api/tests\calculations\test_mass_deviation.py-93-def test_a_float_is_refused_at_the_boundary() -> None:
apps/api/tests\calculations\test_mass_deviation.py-94-    """The engine's standing rule, restated for the new entry point.
apps/api/tests\calculations\test_mass_deviation.py-95-
apps/api/tests\calculations\test_mass_deviation.py-96-    `0.1` is not representable in binary floating point, and a weighing
apps/api/tests\calculations\test_mass_deviation.py:97:    reconciliation is precisely where that error becomes a decision about
apps/api/tests\calculations\test_mass_deviation.py-98-    whether a batch is acceptable.
apps/api/tests\calculations\test_mass_deviation.py-99-    """
apps/api/tests\calculations\test_mass_deviation.py-100-    with pytest.raises(TypeError, match="float"):
apps/api/tests\calculations\test_mass_deviation.py:101:        mass_deviation(1.0, Decimal("1.0"))  # type: ignore[arg-type]
apps/api/tests\calculations\test_mass_deviation.py-102-
apps/api/tests\calculations\test_mass_deviation.py-103-
apps/api/tests\calculations\test_mass_deviation.py-104-@given(planned=masses, actual=masses)
apps/api/tests\calculations\test_mass_deviation.py-105-def test_the_delta_always_reconstructs_the_actual_mass(planned: Decimal, actual: Decimal) -> None:
--
apps/api/tests\calculations\test_mass_deviation.py-108-    The invariant a technician relies on when reading the sheet: the two
apps/api/tests\calculations\test_mass_deviation.py-109-    numbers and the difference between them must agree. Exact under
apps/api/tests\calculations\test_mass_deviation.py-110-    `Decimal`; in float this fails for ordinary values.
apps/api/tests\calculations\test_mass_deviation.py-111-    """
apps/api/tests\calculations\test_mass_deviation.py:112:    result = mass_deviation(planned, actual)
apps/api/tests\calculations\test_mass_deviation.py-113-    assert result.planned_kg + result.delta_kg == result.actual_kg
apps/api/tests\calculations\test_mass_deviation.py-114-
apps/api/tests\calculations\test_mass_deviation.py-115-
apps/api/tests\calculations\test_mass_deviation.py-116-@given(planned=masses)
apps/api/tests\calculations\test_mass_deviation.py-117-def test_weighing_exactly_to_plan_is_always_in_tolerance(planned: Decimal) -> None:
apps/api/tests\calculations\test_mass_deviation.py:118:    """Zero deviation passes at every tolerance, including zero.
apps/api/tests\calculations\test_mass_deviation.py-119-
apps/api/tests\calculations\test_mass_deviation.py-120-    Guards the boundary: `abs(0) <= 0` must hold, or a perfectly weighed
apps/api/tests\calculations\test_mass_deviation.py-121-    line would be flagged under a zero-tolerance batch.
apps/api/tests\calculations\test_mass_deviation.py-122-    """
apps/api/tests\calculations\test_mass_deviation.py:123:    result = mass_deviation(planned, planned, tolerance_percent=Decimal("0"))
apps/api/tests\calculations\test_mass_deviation.py-124-    assert result.delta_kg == 0
apps/api/tests\calculations\test_mass_deviation.py-125-    assert result.delta_percent == 0
apps/api/tests\calculations\test_mass_deviation.py-126-    assert result.within_tolerance is True
--
apps/api/tests\db\test_slice2_stage_gates.py-1-"""Stage-gate configuration (Administration §2).
apps/api/tests\db\test_slice2_stage_gates.py-2-
apps/api/tests\db\test_slice2_stage_gates.py-3-The reorder test is the reason this file exists, and it earned its place
apps/api/tests\db\test_slice2_stage_gates.py:4:immediately: `admin_stage_gates.py` originally claimed a single
apps/api/tests\db\test_slice2_stage_gates.py-5-`UPDATE ... FROM unnest(...) WITH ORDINALITY` was collision-free against
apps/api/tests\db\test_slice2_stage_gates.py-6-`UNIQUE (organization_id, sequence)`, "because a non-deferrable unique
apps/api/tests\db\test_slice2_stage_gates.py-7-constraint is checked once at STATEMENT end".
apps/api/tests\db\test_slice2_stage_gates.py-8-
--
apps/api/tests\db\test_slice2_stage_gates.py-14-    "stage_definitions_org_seq_key"
apps/api/tests\db\test_slice2_stage_gates.py-15-
apps/api/tests\db\test_slice2_stage_gates.py-16-Migration 009 made the constraint DEFERRABLE INITIALLY IMMEDIATE and the
apps/api/tests\db\test_slice2_stage_gates.py-17-route now defers it for its own transaction. The tests below prove all
apps/api/tests\db\test_slice2_stage_gates.py:18:three halves of that: ordinary writes are still checked immediately, a
apps/api/tests\db\test_slice2_stage_gates.py:19:reorder passes through duplicate intermediate states, and the final state
apps/api/tests\db\test_slice2_stage_gates.py-20-is still required to be unique.
apps/api/tests\db\test_slice2_stage_gates.py-21-
apps/api/tests\db\test_slice2_stage_gates.py-22-The lesson generalises: a comment asserting engine semantics is a claim,
apps/api/tests\db\test_slice2_stage_gates.py-23-not a check.
--
apps/api/tests\db\test_slice2_stage_gates.py-102-def test_a_row_by_row_reorder_collides(owner_session, gate_world):
apps/api/tests\db\test_slice2_stage_gates.py-103-    """The failure the single-statement form exists to avoid.
apps/api/tests\db\test_slice2_stage_gates.py-104-
apps/api/tests\db\test_slice2_stage_gates.py-105-    Setting stage 2 to sequence 1 while stage 1 still holds 1 violates the
apps/api/tests\db\test_slice2_stage_gates.py:106:    unique constraint immediately. This is the naive implementation, and
apps/api/tests\db\test_slice2_stage_gates.py-107-    it is proven broken here so the comment in admin_stage_gates.py is
apps/api/tests\db\test_slice2_stage_gates.py-108-    demonstrably true rather than merely plausible.
apps/api/tests\db\test_slice2_stage_gates.py-109-    """
apps/api/tests\db\test_slice2_stage_gates.py-110-    with pytest.raises(IntegrityError):
--
apps/api/tests\db\test_slice2_stage_gates.py-123-def test_reversing_the_whole_pipeline_succeeds_in_one_statement(owner_session, gate_world):
apps/api/tests\db\test_slice2_stage_gates.py-124-    """A full reversal -- every stage collides with another mid-way.
apps/api/tests\db\test_slice2_stage_gates.py-125-
apps/api/tests\db\test_slice2_stage_gates.py-126-    The strongest form of the case: no row keeps its sequence, and every
apps/api/tests\db\test_slice2_stage_gates.py:127:    intermediate assignment duplicates a value still held by another row.
apps/api/tests\db\test_slice2_stage_gates.py-128-
apps/api/tests\db\test_slice2_stage_gates.py-129-    Note what is NOT here: any SET CONSTRAINTS. Making the constraint
apps/api/tests\db\test_slice2_stage_gates.py-130-    DEFERRABLE (migration 009) changes how PostgreSQL enforces it -- from
apps/api/tests\db\test_slice2_stage_gates.py-131-    a per-row index check to a constraint trigger fired at END OF
--
apps/api/tests\db\test_slice2_stage_gates.py-209-        owner_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
apps/api/tests\db\test_slice2_stage_gates.py-210-        owner_session.flush()
apps/api/tests\db\test_slice2_stage_gates.py-211-
apps/api/tests\db\test_slice2_stage_gates.py-212-
apps/api/tests\db\test_slice2_stage_gates.py:213:def test_ordinary_writes_are_still_checked_immediately(owner_session, gate_world):
apps/api/tests\db\test_slice2_stage_gates.py-214-    """INITIALLY IMMEDIATE: nothing outside a reorder became laxer.
apps/api/tests\db\test_slice2_stage_gates.py-215-
apps/api/tests\db\test_slice2_stage_gates.py-216-    Without this, migration 009 would have traded a broken reorder for
apps/api/tests\db\test_slice2_stage_gates.py-217-    duplicate sequences surviving until COMMIT everywhere else -- a wider
--
apps/api/tests\calculations\test_formulation.py-143-            ratio = multiple[code] / mass
apps/api/tests\calculations\test_formulation.py-144-            # RELATIVE tolerance. An absolute 0.01 on the ratio meant 0.125%
apps/api/tests\calculations\test_formulation.py-145-            # at factor 8 and 0.02% at factor 50 — a bound that tightened as
apps/api/tests\calculations\test_formulation.py-146-            # the factor grew, for no reason connected to the maths. It
apps/api/tests\calculations\test_formulation.py:147:            # failed at factor 8 on a 0.15% deviation that is simply the
apps/api/tests\calculations\test_formulation.py-148-            # milligram quantiser doing its job.
apps/api/tests\calculations\test_formulation.py-149-            assert abs(ratio - factor) / factor < Decimal("0.01")
apps/api/tests\calculations\test_formulation.py-150-
apps/api/tests\calculations\test_formulation.py-151-
--
apps/api/tests\calculations\test_formulation.py-165-
apps/api/tests\calculations\test_formulation.py-166-def test_a_batch_too_small_for_its_precision_is_refused():
apps/api/tests\calculations\test_formulation.py-167-    """Refused, not fudged.
apps/api/tests\calculations\test_formulation.py-168-
apps/api/tests\calculations\test_formulation.py:169:    Twelve components at milligram precision cannot express a three-gram
apps/api/tests\calculations\test_formulation.py-170-    batch: every line rounds up to the same step and their sum overshoots.
apps/api/tests\calculations\test_formulation.py-171-    The only honest outcomes are a negative mass, a total that is not the
apps/api/tests\calculations\test_formulation.py-172-    batch, or an error — and the first two are worse.
apps/api/tests\calculations\test_formulation.py-173-    """
--
apps/api/tests\calculations\test_formulation.py-182-    components = [Component(f"RM-{i}", Decimal("8.3333")) for i in range(11)]
apps/api/tests\calculations\test_formulation.py-183-    components.append(Component("RM-11", Decimal("8.3337")))
apps/api/tests\calculations\test_formulation.py-184-    assert total_percentage(components) == Decimal("100")
apps/api/tests\calculations\test_formulation.py-185-
apps/api/tests\calculations\test_formulation.py:186:    with pytest.raises(ValueError, match="cannot be expressed"):
apps/api/tests\calculations\test_formulation.py-187-        scale_to_batch(components, Decimal("0.0061"))
apps/api/tests\calculations\test_formulation.py-188-
apps/api/tests\calculations\test_formulation.py-189-
apps/api/tests\calculations\test_formulation.py-190-def test_the_remainder_lands_on_the_largest_line():
--
apps/api/tests\db\test_011_audit_chain_scope.py-185-        _insert(app_session, org_b, "FORGED")
apps/api/tests\db\test_011_audit_chain_scope.py-186-        app_session.flush()
apps/api/tests\db\test_011_audit_chain_scope.py-187-
apps/api/tests\db\test_011_audit_chain_scope.py-188-    assert "row-level security" in str(exc.value).lower(), (
apps/api/tests\db\test_011_audit_chain_scope.py:189:        f"expected an RLS refusal, got: {exc.value}"
apps/api/tests\db\test_011_audit_chain_scope.py-190-    )
apps/api/tests\db\test_011_audit_chain_scope.py-191-
apps/api/tests\db\test_011_audit_chain_scope.py-192-
apps/api/tests\db\test_011_audit_chain_scope.py-193-def test_a_scoped_session_may_still_write_its_own_rows(app_session):
--
apps/api/tests\db\test_011_audit_chain_scope.py-222-        every time.
apps/api/tests\db\test_011_audit_chain_scope.py-223-
apps/api/tests\db\test_011_audit_chain_scope.py-224-    Neither breaks a test today, so a comment would be read years after it
apps/api/tests\db\test_011_audit_chain_scope.py-225-    stopped being true. This assertion fails the moment the cutover lands,
apps/api/tests\db\test_011_audit_chain_scope.py:226:    in the file that explains what to do about it: give the tail read a
apps/api/tests\db\test_011_audit_chain_scope.py-227-    BYPASSRLS-capable owner, or read the tail through a dedicated
apps/api/tests\db\test_011_audit_chain_scope.py-228-    SECURITY DEFINER helper that is exempt.
apps/api/tests\db\test_011_audit_chain_scope.py-229-    """
apps/api/tests\db\test_011_audit_chain_scope.py-230-    permissive = owner_session.execute(text("SELECT core.rls_permissive()")).scalar_one()
--
apps/api/tests\db\test_011_audit_chain_scope.py-265-    _set_org(app_session, org_b)
apps/api/tests\db\test_011_audit_chain_scope.py-266-    _insert(app_session, org_b, "B2")
apps/api/tests\db\test_011_audit_chain_scope.py-267-
apps/api/tests\db\test_011_audit_chain_scope.py-268-    # Read as the unscoped/permissive branch so the walk is not doing the
apps/api/tests\db\test_011_audit_chain_scope.py:269:    # filtering by accident — the explicit organization_id argument must be
apps/api/tests\db\test_011_audit_chain_scope.py-270-    # what scopes it.
apps/api/tests\db\test_011_audit_chain_scope.py-271-    _set_org(app_session, None)
apps/api/tests\db\test_011_audit_chain_scope.py-272-
apps/api/tests\db\test_011_audit_chain_scope.py-273-    assert verify_chain(app_session, organization_id=org_a, start_id=first - 1) is None, (
--
apps/api/tests\db\test_011_audit_chain_scope.py-297-        _insert(app_session, None, "TENANT_FORGING_A_SYSTEM_ROW")
apps/api/tests\db\test_011_audit_chain_scope.py-298-        app_session.flush()
apps/api/tests\db\test_011_audit_chain_scope.py-299-
apps/api/tests\db\test_011_audit_chain_scope.py-300-    assert "row-level security" in str(exc.value).lower(), (
apps/api/tests\db\test_011_audit_chain_scope.py:301:        f"expected an RLS refusal, got: {exc.value}"
apps/api/tests\db\test_011_audit_chain_scope.py-302-    )
apps/api/tests\db\test_011_audit_chain_scope.py-303-
apps/api/tests\db\test_011_audit_chain_scope.py-304-
apps/api/tests\db\test_011_audit_chain_scope.py-305-def test_an_unscoped_session_may_still_write_system_rows(app_session):
--
apps/api/tests\db\test_011_audit_chain_scope.py-344-        "the chain's first event was deleted and verification still reported "
apps/api/tests\db\test_011_audit_chain_scope.py-345-        "the chain intact — the head of the walk is unauthenticated"
apps/api/tests\db\test_011_audit_chain_scope.py-346-    )
apps/api/tests\db\test_011_audit_chain_scope.py-347-    assert found.event_id == ids[1], (
apps/api/tests\db\test_011_audit_chain_scope.py:348:        f"expected the break at the new head {ids[1]}, got {found.event_id}"
apps/api/tests\db\test_011_audit_chain_scope.py-349-    )
--
apps/api/tests\db\test_002_roles_permissions.py-179-                """
apps/api/tests\db\test_002_roles_permissions.py-180-            )
apps/api/tests\db\test_002_roles_permissions.py-181-        ).all()
apps/api/tests\db\test_002_roles_permissions.py-182-    ]
apps/api/tests\db\test_002_roles_permissions.py:183:    unexpected = [code for code in orphans if code not in ORPHANED_UNTIL_THEIR_SLICE]
apps/api/tests\db\test_002_roles_permissions.py:184:    assert unexpected == [], (
apps/api/tests\db\test_002_roles_permissions.py-185-        "these permissions are held by no role, so no user can ever exercise "
apps/api/tests\db\test_002_roles_permissions.py:186:        f"them: {', '.join(unexpected)}"
apps/api/tests\db\test_002_roles_permissions.py-187-    )
apps/api/tests\db\test_002_roles_permissions.py-188-
apps/api/tests\db\test_002_roles_permissions.py-189-    # The allowlist must not outlive its entries. A permission that HAS
apps/api/tests\db\test_002_roles_permissions.py-190-    # been granted but is still listed here means the list is stale, and a
--
apps/api/tests\db\test_002_roles_permissions.py-220-
apps/api/tests\db\test_002_roles_permissions.py-221-def test_no_role_holds_both_development_and_qa_test_approval(owner_session: Session) -> None:
apps/api/tests\db\test_002_roles_permissions.py-222-    """Independent QA review must be independent of development approval.
apps/api/tests\db\test_002_roles_permissions.py-223-
apps/api/tests\db\test_002_roles_permissions.py:224:    Migration 002 states this and the source it came from is explicit that
apps/api/tests\db\test_002_roles_permissions.py-225-    approval routes may demand DISTINCT persons. One role holding both
apps/api/tests\db\test_002_roles_permissions.py-226-    turns a two-step route into a formality.
apps/api/tests\db\test_002_roles_permissions.py-227-    """
apps/api/tests\db\test_002_roles_permissions.py-228-    conflicted = [
--
apps/api/tests\db\test_002_roles_permissions.py-327-    without renaming it there produces a token whose roles map to nothing,
apps/api/tests\db\test_002_roles_permissions.py-328-    which presents as "this user has no permissions" rather than as a
apps/api/tests\db\test_002_roles_permissions.py-329-    configuration error.
apps/api/tests\db\test_002_roles_permissions.py-330-    """
apps/api/tests\db\test_002_roles_permissions.py:331:    expected = {
apps/api/tests\db\test_002_roles_permissions.py-332-        "product_development_chemist",
apps/api/tests\db\test_002_roles_permissions.py-333-        "product_development_engineer",
apps/api/tests\db\test_002_roles_permissions.py-334-        "product_development_lead",
apps/api/tests\db\test_002_roles_permissions.py-335-        "product_development_director",
--
apps/api/tests\db\test_002_roles_permissions.py-343-    actual = {
apps/api/tests\db\test_002_roles_permissions.py-344-        row[0]
apps/api/tests\db\test_002_roles_permissions.py-345-        for row in owner_session.execute(text("SELECT code FROM core.roles WHERE is_seeded")).all()
apps/api/tests\db\test_002_roles_permissions.py-346-    }
apps/api/tests\db\test_002_roles_permissions.py:347:    assert expected <= actual, f"missing seeded roles: {', '.join(sorted(expected - actual))}"
--
apps/api/tests\db\test_object_ownership.py-174-    )
apps/api/tests\db\test_object_ownership.py-175-
apps/api/tests\db\test_object_ownership.py-176-    # Named, not counted. Drift in the schema list cannot mask a table that
apps/api/tests\db\test_object_ownership.py-177-    # has actually gone missing.
apps/api/tests\db\test_object_ownership.py:178:    expected = {
apps/api/tests\db\test_object_ownership.py-179-        "core.organizations",
apps/api/tests\db\test_object_ownership.py-180-        "core.users",
apps/api/tests\db\test_object_ownership.py-181-        "core.organization_members",
apps/api/tests\db\test_object_ownership.py-182-        "innovation.opportunities",
--
apps/api/tests\db\test_object_ownership.py-203-            ),
apps/api/tests\db\test_object_ownership.py-204-            {"schemas": list(APP_SCHEMAS)},
apps/api/tests\db\test_object_ownership.py-205-        ).all()
apps/api/tests\db\test_object_ownership.py-206-    }
apps/api/tests\db\test_object_ownership.py:207:    assert expected <= found, f"tables missing from the database: {sorted(expected - found)}"
apps/api/tests\db\test_object_ownership.py-208-
apps/api/tests\db\test_object_ownership.py-209-
apps/api/tests\db\test_object_ownership.py-210-def test_security_definer_functions_were_not_swept_along(owner_session: Session) -> None:
apps/api/tests\db\test_object_ownership.py-211-    """`audit.chain_row` owns its privileges; the sweep must not spread that.
--
apps/api/tests\db\test_slice2_opportunities.py-1-"""Opportunities — the head of the digital thread, and its gate.
apps/api/tests\db\test_slice2_opportunities.py-2-
apps/api/tests\db\test_slice2_opportunities.py-3-The assertions that matter most here are the ones about what is REFUSED.
apps/api/tests\db\test_slice2_opportunities.py-4-A gate that can be walked around is not a gate, and every refusal below
apps/api/tests\db\test_slice2_opportunities.py:5:corresponds to a state the digital thread could not explain:
apps/api/tests\db\test_slice2_opportunities.py-6-
apps/api/tests\db\test_slice2_opportunities.py-7-  * a project whose originating opportunity was never approved
apps/api/tests\db\test_slice2_opportunities.py-8-  * two projects claiming the same opportunity
apps/api/tests\db\test_slice2_opportunities.py-9-  * a decision that silently overwrote an earlier one
--
apps/api/tests\db\test_024_memberships_for_subject.py-52-        .all()
apps/api/tests\db\test_024_memberships_for_subject.py-53-    )
apps/api/tests\db\test_024_memberships_for_subject.py-54-
apps/api/tests\db\test_024_memberships_for_subject.py-55-    # `pg_get_function_identity_arguments` includes the parameter NAME, so
apps/api/tests\db\test_024_memberships_for_subject.py:56:    # the expected value is "p_sub text" and not "text". Asserted as the
apps/api/tests\db\test_024_memberships_for_subject.py-57-    # full string rather than a substring: an added second parameter would
apps/api/tests\db\test_024_memberships_for_subject.py-58-    # still contain "p_sub text".
apps/api/tests\db\test_024_memberships_for_subject.py-59-    assert signatures == ["p_sub text"], (
apps/api/tests\db\test_024_memberships_for_subject.py:60:        f"expected exactly one signature taking only the subject, found {signatures}"
apps/api/tests\db\test_024_memberships_for_subject.py-61-    )
apps/api/tests\db\test_024_memberships_for_subject.py-62-
apps/api/tests\db\test_024_memberships_for_subject.py-63-
apps/api/tests\db\test_024_memberships_for_subject.py-64-def test_execute_is_not_public(owner_session) -> None:
--
apps/api/tests\db\test_024_memberships_for_subject.py-88-    The worker never serves `/api/me`. An RLS-bypassing lookup that worker
apps/api/tests\db\test_024_memberships_for_subject.py-89-    code can call for an arbitrary subject is an identity-enumeration
apps/api/tests\db\test_024_memberships_for_subject.py-90-    primitive sitting in a process with no use for it.
apps/api/tests\db\test_024_memberships_for_subject.py-91-    """
apps/api/tests\db\test_024_memberships_for_subject.py:92:    for role, expected in (("evercoat_app", True), ("evercoat_worker", False)):
apps/api/tests\db\test_024_memberships_for_subject.py-93-        granted = owner_session.execute(
apps/api/tests\db\test_024_memberships_for_subject.py-94-            text(
apps/api/tests\db\test_024_memberships_for_subject.py-95-                "SELECT has_function_privilege(:role, "
apps/api/tests\db\test_024_memberships_for_subject.py-96-                "'core.memberships_for_subject(text)', 'EXECUTE')"
apps/api/tests\db\test_024_memberships_for_subject.py-97-            ),
apps/api/tests\db\test_024_memberships_for_subject.py-98-            {"role": role},
apps/api/tests\db\test_024_memberships_for_subject.py-99-        ).scalar_one()
apps/api/tests\db\test_024_memberships_for_subject.py:100:        assert granted is expected, (
apps/api/tests\db\test_024_memberships_for_subject.py:101:            f"{role} EXECUTE on core.memberships_for_subject is {granted}, expected {expected}"
apps/api/tests\db\test_024_memberships_for_subject.py-102-        )
apps/api/tests\db\test_024_memberships_for_subject.py-103-
apps/api/tests\db\test_024_memberships_for_subject.py-104-
apps/api/tests\db\test_024_memberships_for_subject.py-105-def test_the_definer_is_pinned(owner_session) -> None:
apps/api/tests\db\test_024_memberships_for_subject.py-106-    """SECURITY DEFINER means "run as the OWNER", so the owner must be fixed.
apps/api/tests\db\test_024_memberships_for_subject.py-107-
apps/api/tests\db\test_024_memberships_for_subject.py:108:    Without an explicit ``ALTER FUNCTION ... OWNER TO``, the definer is
apps/api/tests\db\test_024_memberships_for_subject.py-109-    whichever account happened to run the migration -- ``postgres`` in CI,
apps/api/tests\db\test_024_memberships_for_subject.py-110-    something else elsewhere -- and the function then behaves differently
apps/api/tests\db\test_024_memberships_for_subject.py-111-    per environment. See migration 024.
apps/api/tests\db\test_024_memberships_for_subject.py-112-    """
--
apps/api/tests\db\test_024_memberships_for_subject.py-158-    this one lookup -- is a decision that belongs with the cutover
apps/api/tests\db\test_024_memberships_for_subject.py-159-    migration and its review, not smuggled in ahead of it.
apps/api/tests\db\test_024_memberships_for_subject.py-160-
apps/api/tests\db\test_024_memberships_for_subject.py-161-    This assertion fails the moment the cutover lands, in the file that
apps/api/tests\db\test_024_memberships_for_subject.py:162:    explains what to do about it.
apps/api/tests\db\test_024_memberships_for_subject.py-163-    """
apps/api/tests\db\test_024_memberships_for_subject.py-164-    permissive = owner_session.execute(text("SELECT core.rls_permissive()")).scalar_one()
apps/api/tests\db\test_024_memberships_for_subject.py-165-    forced = owner_session.execute(
apps/api/tests\db\test_024_memberships_for_subject.py-166-        text(
--
apps/api/tests\db\test_023_messaging.py-12-somebody with no access to it. The test below is the one that would have
apps/api/tests\db\test_023_messaging.py-13-caught it.
apps/api/tests\db\test_023_messaging.py-14-
apps/api/tests\db\test_023_messaging.py-15-**Informal chat never becomes authoritative knowledge automatically**
apps/api/tests\db\test_023_messaging.py:16:(§7). Promotion exists, is explicit, produces a TASK rather than a
apps/api/tests\db\test_023_messaging.py-17-conclusion, and links back to the message it came from.
apps/api/tests\db\test_023_messaging.py-18-
apps/api/tests\db\test_023_messaging.py-19-Everything here runs on `app_session` where the boundary is the subject,
apps/api/tests\db\test_023_messaging.py-20-because the owner is exempt from RLS while `relforcerowsecurity` is FALSE
--
apps/api/tests\db\test_023_messaging.py-261-
apps/api/tests\db\test_023_messaging.py-262-def test_promotion_creates_a_task_and_links_back_to_the_message(
apps/api/tests\db\test_023_messaging.py-263-    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests\db\test_023_messaging.py-264-) -> None:
apps/api/tests\db\test_023_messaging.py:265:    """§7: conclusions become controlled records only by explicit human
apps/api/tests\db\test_023_messaging.py-266-    promotion -- and what they become is a TASK, not a decision.
apps/api/tests\db\test_023_messaging.py-267-
apps/api/tests\db\test_023_messaging.py-268-    The link back is the digital thread's rule applied to conversation:
apps/api/tests\db\test_023_messaging.py-269-    the task can always answer "where did this come from?".
--
apps/api/tests\db\test_023_messaging.py-288-        app_session,
apps/api/tests\db\test_023_messaging.py-289-        message_id=message["id"],
apps/api/tests\db\test_023_messaging.py-290-        organization_id=fx["org"],
apps/api/tests\db\test_023_messaging.py-291-        actor_id=fx["author"],
apps/api/tests\db\test_023_messaging.py:292:        task_type="experiment",
apps/api/tests\db\test_023_messaging.py-293-        title="Re-run adhesion at 5 C",
apps/api/tests\db\test_023_messaging.py-294-    )
apps/api/tests\db\test_023_messaging.py-295-    app_session.commit()
apps/api/tests\db\test_023_messaging.py-296-
--
apps/api/tests\db\test_022_msd_boundary.py-140-    # MSD turns and evidence are append-only IN THE DATABASE -- 022 puts
apps/api/tests\db\test_022_msd_boundary.py-141-    # `audit.deny_mutation()` on both, which is the whole point: an
apps/api/tests\db\test_022_msd_boundary.py-142-    # answer's cited sources cannot be quietly removed after the fact.
apps/api/tests\db\test_022_msd_boundary.py-143-    # That guard applies to this teardown too, so the triggers are
apps/api/tests\db\test_022_msd_boundary.py:144:    # disabled around the delete and re-enabled immediately. Disabling
apps/api/tests\db\test_022_msd_boundary.py-145-    # them is itself proof the mechanism is real; a fixture that could
apps/api/tests\db\test_022_msd_boundary.py-146-    # just delete would mean the guard was decorative.
apps/api/tests\db\test_022_msd_boundary.py-147-    owner_session.execute(
apps/api/tests\db\test_022_msd_boundary.py-148-        text("ALTER TABLE ai.msd_evidence DISABLE TRIGGER msd_evidence_append_only")
--
apps/api/tests\db\test_022_msd_boundary.py-374-) -> None:
apps/api/tests\db\test_022_msd_boundary.py-375-    """§7: AI recommendations are labelled, always.
apps/api/tests\db\test_022_msd_boundary.py-376-
apps/api/tests\db\test_022_msd_boundary.py-377-    Enforced by a CHECK constraint rather than by a template, so a turn
apps/api/tests\db\test_022_msd_boundary.py:378:    read through the API, exported or printed carries the label too — a
apps/api/tests\db\test_022_msd_boundary.py-379-    template only decorates one rendering of it.
apps/api/tests\db\test_022_msd_boundary.py-380-    """
apps/api/tests\db\test_022_msd_boundary.py-381-    from sqlalchemy.exc import IntegrityError
apps/api/tests\db\test_022_msd_boundary.py-382-
--
apps/api/tests\auth\test_token_verification.py-4-exactly why they need testing: the question is not "does a valid token
apps/api/tests\auth\test_token_verification.py-5-work" but "does an invalid one get refused". A verifier that accepts
apps/api/tests\auth\test_token_verification.py-6-anything passes the happy path perfectly.
apps/api/tests\auth\test_token_verification.py-7-
apps/api/tests\auth\test_token_verification.py:8:`SECURITY.md` §2 requires signature, issuer, audience AND expiry to all
apps/api/tests\auth\test_token_verification.py-9-be verified. Each is asserted separately below, so a regression names the
apps/api/tests\auth\test_token_verification.py-10-specific check that lapsed rather than just "auth broke".
apps/api/tests\auth\test_token_verification.py-11-"""
apps/api/tests\auth\test_token_verification.py-12-
--
apps/api/tests\auth\test_token_verification.py-28-    claims = await _decode(token)
apps/api/tests\auth\test_token_verification.py-29-    assert claims["sub"] == "user-123"
apps/api/tests\auth\test_token_verification.py-30-
apps/api/tests\auth\test_token_verification.py-31-
apps/api/tests\auth\test_token_verification.py:32:async def test_expired_token_is_refused(make_token):
apps/api/tests\auth\test_token_verification.py-33-    # The single most important negative case: an access token that
apps/api/tests\auth\test_token_verification.py:34:    # outlives its expiry is a stolen credential with no shelf life.
apps/api/tests\auth\test_token_verification.py:35:    token = make_token(expires_in=-60)
apps/api/tests\auth\test_token_verification.py-36-    with pytest.raises(HTTPException) as exc:
apps/api/tests\auth\test_token_verification.py-37-        await _decode(token)
apps/api/tests\auth\test_token_verification.py-38-    assert exc.value.status_code == 401
apps/api/tests\auth\test_token_verification.py-39-
apps/api/tests\auth\test_token_verification.py-40-
apps/api/tests\auth\test_token_verification.py-41-async def test_wrong_audience_is_refused(make_token):
apps/api/tests\auth\test_token_verification.py-42-    # A token minted for the web client must not be accepted by the API.
apps/api/tests\auth\test_token_verification.py-43-    # Keycloak issues both; only the audience distinguishes them, which
apps/api/tests\auth\test_token_verification.py:44:    # is why the realm needs an explicit audience mapper.
apps/api/tests\auth\test_token_verification.py-45-    token = make_token(audience="some-other-client")
apps/api/tests\auth\test_token_verification.py-46-    with pytest.raises(HTTPException) as exc:
apps/api/tests\auth\test_token_verification.py-47-        await _decode(token)
apps/api/tests\auth\test_token_verification.py-48-    assert exc.value.status_code == 401
--
apps/api/tests\auth\test_token_verification.py-61-async def test_token_signed_by_another_key_is_refused(make_token, jwks):
apps/api/tests\auth\test_token_verification.py-62-    from cryptography.hazmat.primitives import serialization
apps/api/tests\auth\test_token_verification.py-63-    from cryptography.hazmat.primitives.asymmetric import rsa
apps/api/tests\auth\test_token_verification.py-64-
apps/api/tests\auth\test_token_verification.py:65:    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
apps/api/tests\auth\test_token_verification.py-66-    pem = attacker.private_bytes(
apps/api/tests\auth\test_token_verification.py-67-        encoding=serialization.Encoding.PEM,
apps/api/tests\auth\test_token_verification.py-68-        format=serialization.PrivateFormat.PKCS8,
apps/api/tests\auth\test_token_verification.py:69:        encryption_algorithm=serialization.NoEncryption(),
apps/api/tests\auth\test_token_verification.py-70-    ).decode()
apps/api/tests\auth\test_token_verification.py-71-
apps/api/tests\auth\test_token_verification.py-72-    now = int(time.time())
apps/api/tests\auth\test_token_verification.py-73-    forged = jwt.encode(
apps/api/tests\auth\test_token_verification.py-74-        {
apps/api/tests\auth\test_token_verification.py-75-            "sub": "attacker",
apps/api/tests\auth\test_token_verification.py-76-            "iss": "http://localhost:18080/realms/evercoat",
apps/api/tests\auth\test_token_verification.py-77-            "aud": "evercoat-api",
apps/api/tests\auth\test_token_verification.py:78:            "iat": now,
apps/api/tests\auth\test_token_verification.py:79:            "exp": now + 300,
apps/api/tests\auth\test_token_verification.py-80-        },
apps/api/tests\auth\test_token_verification.py-81-        pem,
apps/api/tests\auth\test_token_verification.py:82:        algorithm="RS256",
apps/api/tests\auth\test_token_verification.py:83:        headers={"kid": "test-key-1"},  # claims to be our key
apps/api/tests\auth\test_token_verification.py-84-    )
apps/api/tests\auth\test_token_verification.py-85-
apps/api/tests\auth\test_token_verification.py-86-    with pytest.raises(HTTPException) as exc:
apps/api/tests\auth\test_token_verification.py-87-        await _decode(forged)
apps/api/tests\auth\test_token_verification.py-88-    assert exc.value.status_code == 401
apps/api/tests\auth\test_token_verification.py-89-
apps/api/tests\auth\test_token_verification.py-90-
apps/api/tests\auth\test_token_verification.py-91-async def test_unsigned_token_is_refused():
apps/api/tests\auth\test_token_verification.py:92:    """The alg=none attack.
apps/api/tests\auth\test_token_verification.py-93-
apps/api/tests\auth\test_token_verification.py:94:    A verifier that honours the token's own algorithm header can be told
apps/api/tests\auth\test_token_verification.py-95-    not to check the signature at all. `_decode` pins
apps/api/tests\auth\test_token_verification.py:96:    ``algorithms=["RS256"]``, so this must fail — and if someone ever
apps/api/tests\auth\test_token_verification.py-97-    widens that list to include "none", this test is what catches it.
apps/api/tests\auth\test_token_verification.py-98-
apps/api/tests\auth\test_token_verification.py-99-    Hand-built rather than minted with python-jose, because python-jose
apps/api/tests\auth\test_token_verification.py:100:    refuses to *encode* alg=none. That refusal is a good default and
apps/api/tests\auth\test_token_verification.py-101-    proves nothing about our verifier: an attacker does not use our
apps/api/tests\auth\test_token_verification.py-102-    library. The wire format is just
apps/api/tests\auth\test_token_verification.py-103-    ``base64url(header).base64url(payload).`` with an empty signature,
apps/api/tests\auth\test_token_verification.py-104-    which is trivial to produce with a text editor.
--
apps/api/tests\auth\test_token_verification.py-109-    def b64(data: dict[str, object]) -> str:
apps/api/tests\auth\test_token_verification.py-110-        raw = json.dumps(data, separators=(",", ":")).encode()
apps/api/tests\auth\test_token_verification.py-111-        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
apps/api/tests\auth\test_token_verification.py-112-
apps/api/tests\auth\test_token_verification.py:113:    header = b64({"alg": "none", "typ": "JWT"})
apps/api/tests\auth\test_token_verification.py-114-    payload = b64(
apps/api/tests\auth\test_token_verification.py-115-        {
apps/api/tests\auth\test_token_verification.py-116-            "sub": "attacker",
apps/api/tests\auth\test_token_verification.py-117-            "iss": "http://localhost:18080/realms/evercoat",
apps/api/tests\auth\test_token_verification.py-118-            "aud": "evercoat-api",
apps/api/tests\auth\test_token_verification.py:119:            "exp": int(time.time()) + 300,
apps/api/tests\auth\test_token_verification.py-120-        }
apps/api/tests\auth\test_token_verification.py-121-    )
apps/api/tests\auth\test_token_verification.py-122-    unsigned = f"{header}.{payload}."
apps/api/tests\auth\test_token_verification.py-123-
--
apps/api/tests\auth\test_token_verification.py-134-
apps/api/tests\auth\test_token_verification.py-135-async def test_refusal_does_not_leak_why(make_token):
apps/api/tests\auth\test_token_verification.py-136-    """The 401 body must not distinguish failure modes.
apps/api/tests\auth\test_token_verification.py-137-
apps/api/tests\auth\test_token_verification.py:138:    "expired" versus "wrong audience" versus "bad signature" tells an
apps/api/tests\auth\test_token_verification.py-139-    attacker which part of the token to fix next. All three return the
apps/api/tests\auth\test_token_verification.py-140-    same opaque detail.
apps/api/tests\auth\test_token_verification.py-141-    """
apps/api/tests\auth\test_token_verification.py-142-    cases = [
apps/api/tests\auth\test_token_verification.py:143:        make_token(expires_in=-60),
apps/api/tests\auth\test_token_verification.py-144-        make_token(audience="wrong"),
apps/api/tests\auth\test_token_verification.py-145-        make_token(issuer="http://wrong"),
apps/api/tests\auth\test_token_verification.py-146-    ]
apps/api/tests\auth\test_token_verification.py-147-    details = set()
--
apps/api/tests\db\test_018_testing.py-71-
apps/api/tests\db\test_018_testing.py-72-    A field with no route cannot be posted — but an absence is invisible
apps/api/tests\db\test_018_testing.py-73-    in a diff, and the next person to add a convenience endpoint would
apps/api/tests\db\test_018_testing.py-74-    not know. This reads the whole OpenAPI schema, so it fails wherever
apps/api/tests\db\test_018_testing.py:75:    the field reappears rather than only where it was expected.
apps/api/tests\db\test_018_testing.py-76-
apps/api/tests\db\test_018_testing.py-77-    Takes no fixtures deliberately: it must run even where no database is
apps/api/tests\db\test_018_testing.py-78-    reachable, because it is checking the shape of the API and not the
apps/api/tests\db\test_018_testing.py-79-    contents of a table.
--
apps/api/tests\db\test_018_testing.py-121-        / "migrations"
apps/api/tests\db\test_018_testing.py-122-        / "018_testing_methods_tests_replicates.sql"
apps/api/tests\db\test_018_testing.py-123-    ).read_text(encoding="utf-8")
apps/api/tests\db\test_018_testing.py-124-
apps/api/tests\db\test_018_testing.py:125:    for column, expected in (
apps/api/tests\db\test_018_testing.py-126-        ("execution_status", EXECUTION_STATUSES),
apps/api/tests\db\test_018_testing.py-127-        ("validity_status", VALIDITY_STATUSES),
apps/api/tests\db\test_018_testing.py-128-        ("calculated_result", CALCULATED_RESULTS),
apps/api/tests\db\test_018_testing.py-129-        ("review_state", REVIEW_STATES),
apps/api/tests\db\test_018_testing.py-130-        ("approval_state", APPROVAL_STATES),
apps/api/tests\db\test_018_testing.py-131-    ):
apps/api/tests\db\test_018_testing.py:132:        for value in expected:
apps/api/tests\db\test_018_testing.py-133-            assert f"'{value}'" in sql, (
apps/api/tests\db\test_018_testing.py-134-                f"the engine allows {column} = '{value}' and migration 018 never "
apps/api/tests\db\test_018_testing.py-135-                "mentions it; a row the traffic light can reason about could not "
apps/api/tests\db\test_018_testing.py-136-                "be stored"
--
apps/api/tests\db\test_018_testing.py-743-    """🔴 RULE 6 OF THE SEVEN, THROUGH THE WHOLE STACK.
apps/api/tests\db\test_018_testing.py-744-
apps/api/tests\db\test_018_testing.py-745-    The engine's unit tests prove rule 12 in isolation. This proves the
apps/api/tests\db\test_018_testing.py-746-    service assembles the inputs correctly from real rows — that the
apps/api/tests\db\test_018_testing.py:747:    disposition a screen would receive is the one the algorithm intends.
apps/api/tests\db\test_018_testing.py-748-    """
apps/api/tests\db\test_018_testing.py-749-    fx = testable
apps/api/tests\db\test_018_testing.py-750-    test_id = _plan(owner_session, fx)
apps/api/tests\db\test_018_testing.py-751-    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
--
apps/api/tests\auth\test_slice2_planning_routes.py-201-    """RLS gives no protection here at all.
apps/api/tests\auth\test_slice2_planning_routes.py-202-
apps/api/tests\auth\test_slice2_planning_routes.py-203-    `risks.owner_user_id` is a plain FK to `core.users`, users are not
apps/api/tests\auth\test_slice2_planning_routes.py-204-    tenant-scoped, and referential integrity bypasses RLS even under
apps/api/tests\auth\test_slice2_planning_routes.py:205:    FORCE. Only the explicit membership check stands between this request
apps/api/tests\auth\test_slice2_planning_routes.py-206-    and another tenant's user being named on this dashboard.
apps/api/tests\auth\test_slice2_planning_routes.py-207-    """
apps/api/tests\auth\test_slice2_planning_routes.py-208-    r = client.post(
apps/api/tests\auth\test_slice2_planning_routes.py-209-        f"/api/projects/{lead_ctx['mine']}/risks",
--
apps/api/tests\db\test_pipeline_history.py-76-
apps/api/tests\db\test_pipeline_history.py-77-    # audit.events is deliberately NOT cleaned up: it is append-only by
apps/api/tests\db\test_pipeline_history.py-78-    # trigger, and an earlier version of this teardown tried to delete
apps/api/tests\db\test_pipeline_history.py-79-    # from it. The trigger raised (correctly), the rollback discarded the
apps/api/tests\db\test_pipeline_history.py:80:    # transaction, and every subsequent delete failed -- one expected
apps/api/tests\db\test_pipeline_history.py-81-    # refusal became nine teardown errors that looked like real failures.
apps/api/tests\db\test_pipeline_history.py-82-    # Audit rows carry no FK to these tables, so leaving them is harmless.
apps/api/tests\db\test_pipeline_history.py-83-    #
apps/api/tests\db\test_pipeline_history.py-84-    # rollback() rather than begin(): the test body's queries autobegan a
apps/api/tests\db\test_pipeline_history.py:85:    # transaction, so an explicit begin() here raises "a transaction is
apps/api/tests\db\test_pipeline_history.py-86-    # already begun". Rolling back ends whatever is open and lets the
apps/api/tests\db\test_pipeline_history.py-87-    # deletes below autobegin cleanly.
apps/api/tests\db\test_pipeline_history.py-88-    owner_session.rollback()
apps/api/tests\db\test_pipeline_history.py-89-    for stmt in [
--
apps/api/tests\auth\test_authorization.py-34-
apps/api/tests\auth\test_authorization.py-35-
apps/api/tests\auth\test_authorization.py-36-@pytest.fixture
apps/api/tests\auth\test_authorization.py-37-def api(seeded_org):
apps/api/tests\auth\test_authorization.py:38:    """A minimal app exposing one route per authorization pattern."""
apps/api/tests\auth\test_authorization.py-39-    app = FastAPI()
apps/api/tests\auth\test_authorization.py-40-
apps/api/tests\auth\test_authorization.py-41-    @app.get("/open")
apps/api/tests\auth\test_authorization.py-42-    def open_route(p: Principal = Depends(get_principal)) -> dict[str, str]:
--
apps/api/tests\auth\test_authorization.py-149-    )
apps/api/tests\auth\test_authorization.py-150-    assert r.status_code == 403
apps/api/tests\auth\test_authorization.py-151-
apps/api/tests\auth\test_authorization.py-152-
apps/api/tests\auth\test_authorization.py:153:def test_revoking_membership_takes_effect_immediately(api, make_token, seeded_org, owner_session):
apps/api/tests\auth\test_authorization.py-154-    """A live token must stop working when membership is revoked.
apps/api/tests\auth\test_authorization.py-155-
apps/api/tests\auth\test_authorization.py-156-    Permissions are read from the database per request rather than
apps/api/tests\auth\test_authorization.py-157-    trusted from token claims precisely so that revocation bites now
apps/api/tests\auth\test_authorization.py:158:    rather than whenever the access token happens to expire. A 5-minute
apps/api/tests\auth\test_authorization.py-159-    window in which a removed user retains formulation access is not
apps/api/tests\auth\test_authorization.py-160-    acceptable.
apps/api/tests\auth\test_authorization.py-161-    """
apps/api/tests\auth\test_authorization.py-162-    token = make_token(sub=seeded_org["keycloak_sub"])
--
apps/api/tests\auth\test_authorization.py-197-    """The defect F32 named.
apps/api/tests\auth\test_authorization.py-198-
apps/api/tests\auth\test_authorization.py-199-    Same organization, holds the permission, is simply not on the
apps/api/tests\auth\test_authorization.py-200-    project. Before ADR-016 nothing but application code stopped this,
apps/api/tests\auth\test_authorization.py:201:    so a single missing dependency exposed another team's formulations
apps/api/tests\auth\test_authorization.py-202-    to a colleague.
apps/api/tests\auth\test_authorization.py-203-    """
apps/api/tests\auth\test_authorization.py-204-    token = make_token(sub=seeded_org["keycloak_sub"])
apps/api/tests\auth\test_authorization.py-205-    r = api.get(
--
apps/api/tests\db\test_requirements.py-271-    assert [r["criticality"] for r in matrix["requirements"]] == ["critical", "minor"]
apps/api/tests\db\test_requirements.py-272-
apps/api/tests\db\test_requirements.py-273-
apps/api/tests\db\test_requirements.py-274-def test_matrix_states_that_tests_are_unavailable(owner_session, req_project):
apps/api/tests\db\test_requirements.py:275:    """The gap must be explicit.
apps/api/tests\db\test_requirements.py-276-
apps/api/tests\db\test_requirements.py-277-    'No requirement has passed' and 'we cannot yet tell' are different
apps/api/tests\db\test_requirements.py-278-    claims, and a matrix that silently omits the distinction is one
apps/api/tests\db\test_requirements.py-279-    nobody notices is empty.
--
apps/api/tests\auth\conftest.py-1-"""Fixtures for authorization tests.
apps/api/tests\auth\conftest.py-2-
apps/api/tests\auth\conftest.py-3-These run without Keycloak. A generated RSA keypair signs tokens and a
apps/api/tests\auth\conftest.py:4:patched JWKS serves the public half, which tests the verification path
apps/api/tests\auth\conftest.py-5-*more* thoroughly than pointing at a real server would: it can mint the
apps/api/tests\auth\conftest.py:6:tokens a real Keycloak will not issue on demand — expired, wrong
apps/api/tests\auth\conftest.py-7-audience, wrong issuer, unsigned, signed by the wrong key.
apps/api/tests\auth\conftest.py-8-
apps/api/tests\auth\conftest.py-9-CI has no Keycloak service either, so this is also the only way these
apps/api/tests\auth\conftest.py-10-paths get exercised there.
--
apps/api/tests\auth\conftest.py-27-
apps/api/tests\auth\conftest.py-28-
apps/api/tests\auth\conftest.py-29-@pytest.fixture(scope="session")
apps/api/tests\auth\conftest.py-30-def rsa_key() -> rsa.RSAPrivateKey:
apps/api/tests\auth\conftest.py:31:    return rsa.generate_private_key(public_exponent=65537, key_size=2048)
apps/api/tests\auth\conftest.py-32-
apps/api/tests\auth\conftest.py-33-
apps/api/tests\auth\conftest.py-34-@pytest.fixture(scope="session")
apps/api/tests\auth\conftest.py-35-def private_pem(rsa_key: rsa.RSAPrivateKey) -> str:
apps/api/tests\auth\conftest.py-36-    return rsa_key.private_bytes(
apps/api/tests\auth\conftest.py-37-        encoding=serialization.Encoding.PEM,
apps/api/tests\auth\conftest.py-38-        format=serialization.PrivateFormat.PKCS8,
apps/api/tests\auth\conftest.py:39:        encryption_algorithm=serialization.NoEncryption(),
apps/api/tests\auth\conftest.py-40-    ).decode()
apps/api/tests\auth\conftest.py-41-
apps/api/tests\auth\conftest.py-42-
apps/api/tests\auth\conftest.py-43-@pytest.fixture(scope="session")
--
apps/api/tests\auth\conftest.py-55-        "keys": [
apps/api/tests\auth\conftest.py-56-            {
apps/api/tests\auth\conftest.py-57-                "kty": "RSA",
apps/api/tests\auth\conftest.py-58-                "use": "sig",
apps/api/tests\auth\conftest.py:59:                "alg": "RS256",
apps/api/tests\auth\conftest.py:60:                "kid": KID,
apps/api/tests\auth\conftest.py-61-                "n": b64(numbers.n),
apps/api/tests\auth\conftest.py-62-                "e": b64(numbers.e),
apps/api/tests\auth\conftest.py-63-            }
apps/api/tests\auth\conftest.py-64-        ]
--
apps/api/tests\auth\conftest.py-77-        *,
apps/api/tests\auth\conftest.py-78-        sub: str | None = None,
apps/api/tests\auth\conftest.py-79-        issuer: str = TEST_ISSUER,
apps/api/tests\auth\conftest.py-80-        audience: str = TEST_AUDIENCE,
apps/api/tests\auth\conftest.py:81:        expires_in: int = 300,
apps/api/tests\auth\conftest.py:82:        algorithm: str = "RS256",
apps/api/tests\auth\conftest.py-83-        extra: dict[str, Any] | None = None,
apps/api/tests\auth\conftest.py-84-    ) -> str:
apps/api/tests\auth\conftest.py-85-        now = int(time.time())
apps/api/tests\auth\conftest.py-86-        claims: dict[str, Any] = {
apps/api/tests\auth\conftest.py-87-            "sub": sub or str(uuid.uuid4()),
apps/api/tests\auth\conftest.py-88-            "iss": issuer,
apps/api/tests\auth\conftest.py-89-            "aud": audience,
apps/api/tests\auth\conftest.py:90:            "iat": now,
apps/api/tests\auth\conftest.py:91:            "exp": now + expires_in,
apps/api/tests\auth\conftest.py-92-            "sid": str(uuid.uuid4()),
apps/api/tests\auth\conftest.py-93-        }
apps/api/tests\auth\conftest.py-94-        if extra:
apps/api/tests\auth\conftest.py-95-            claims.update(extra)
apps/api/tests\auth\conftest.py:96:        return jwt.encode(claims, private_pem, algorithm=algorithm, headers={"kid": KID})
apps/api/tests\auth\conftest.py-97-
apps/api/tests\auth\conftest.py-98-    return _make
apps/api/tests\auth\conftest.py-99-
apps/api/tests\auth\conftest.py-100-
apps/api/tests\auth\conftest.py-101-@pytest.fixture(autouse=True)
apps/api/tests\auth\conftest.py-102-def _patch_jwks(monkeypatch, jwks: dict[str, Any]):
apps/api/tests\auth\conftest.py:103:    """Serve the generated JWKS instead of fetching from Keycloak.
apps/api/tests\auth\conftest.py-104-
apps/api/tests\auth\conftest.py-105-    Patched at the module boundary rather than by stubbing HTTP, so the
apps/api/tests\auth\conftest.py:106:    real ``jwt.decode`` call — signature, issuer, audience and expiry —
apps/api/tests\auth\conftest.py-107-    still runs. Stubbing the decode itself would test nothing.
apps/api/tests\auth\conftest.py-108-    """
apps/api/tests\auth\conftest.py-109-    import app.core.security as security
apps/api/tests\auth\conftest.py-110-
--
apps/api/tests\auth\conftest.py-281-
apps/api/tests\auth\conftest.py-282-    owner_session.rollback()
apps/api/tests\auth\conftest.py-283-    # stage_transitions is append-only by trigger -- the same design that
apps/api/tests\auth\conftest.py-284-    # makes the history trustworthy also makes it undeletable. Tests must
apps/api/tests\auth\conftest.py:285:    # disable the trigger explicitly (as owner) rather than discovering
apps/api/tests\auth\conftest.py-286-    # the refusal in teardown, where it cascades: the raise poisons the
apps/api/tests\auth\conftest.py:287:    # transaction and every subsequent delete fails, turning one expected
apps/api/tests\auth\conftest.py-288-    # refusal into a wall of errors that look like real failures.
apps/api/tests\auth\conftest.py-289-    owner_session.execute(
apps/api/tests\auth\conftest.py-290-        text("ALTER TABLE workflow.stage_transitions DISABLE TRIGGER stage_transitions_immutable")
apps/api/tests\auth\conftest.py-291-    )
--
reviews/codex-slice7-messaging-auth.md-28-
reviews/codex-slice7-messaging-auth.md-29-Report concrete defects with file:line. State clearly if a category has none. Do not review files outside the list.
reviews/codex-slice7-messaging-auth.md-30-
reviews/codex-slice7-messaging-auth.md-31-codex
reviews/codex-slice7-messaging-auth.md:32:I’ll inspect only the six specified files and trace the relevant call/data paths. I’ll keep the review read-only and report only concrete defects or explicit “none” findings by category.
reviews/codex-slice7-messaging-auth.md-33-2026-08-19T00:52:34.317676Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'apps/api/app/domains/messaging/service.py','apps/api/app/api/messaging.py','scripts/keycloak-bootstrap.sh','scripts/keycloak-bind-subs.py','.github/workflows/ci.yml','apps/api/tests/db/test_023_messaging.py'); foreach ("'$f in $files) { Write-Output "FILE $f"; $n=0; Get-Content -LiteralPath $f | ForEach-Object { $n++; '"'{0,5}: {1}' -f "'$n, $_ } }'` rejected: blocked by policy
reviews/codex-slice7-messaging-auth.md-34-exec
reviews/codex-slice7-messaging-auth.md-35-"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'apps/api/app/domains/messaging/service.py','apps/api/app/api/messaging.py','scripts/keycloak-bootstrap.sh','scripts/keycloak-bind-subs.py','.github/workflows/ci.yml','apps/api/tests/db/test_023_messaging.py'); foreach ("'$f in $files) { Write-Output "FILE $f"; $n=0; Get-Content -LiteralPath $f | ForEach-Object { $n++; '"'{0,5}: {1}' -f "'$n, $_ } }' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
reviews/codex-slice7-messaging-auth.md-36- declined in 0ms:
--
reviews/codex-slice7-messaging-auth.md-51-scripts/keycloak-bind-subs.py:9:`WHERE u.keycloak_sub = :sub`, where `:sub` is the token's real subject,
reviews/codex-slice7-messaging-auth.md-52-scripts/keycloak-bind-subs.py:10:a UUID minted by Keycloak.
reviews/codex-slice7-messaging-auth.md-53-scripts/keycloak-bind-subs.py:11:
reviews/codex-slice7-messaging-auth.md-54-scripts/keycloak-bind-subs.py:12:Those two never meet. A perfectly valid token -- correct signature,
reviews/codex-slice7-messaging-auth.md:55:scripts/keycloak-bind-subs.py:13:correct issuer, correct audience, unexpired -- resolves to no row, and
reviews/codex-slice7-messaging-auth.md-56-scripts/keycloak-bind-subs.py:14:the API answers 403 "not a member of the requested organization". The
reviews/codex-slice7-messaging-auth.md-57-scripts/keycloak-bind-subs.py:15:authentication is right, the authorization lookup is right, and the
reviews/codex-slice7-messaging-auth.md-58-scripts/keycloak-bind-subs.py:16:system is unusable, because two literals in two files cannot be
reviews/codex-slice7-messaging-auth.md-59-scripts/keycloak-bind-subs.py:17:type-checked into agreement.
--
reviews/codex-slice7-messaging-auth.md-351-apps/api/app/api/messaging.py:199:) -> dict[str, Any]:
reviews/codex-slice7-messaging-auth.md-352-apps/api/app/api/messaging.py:200:    """The only route here that requires a permission.
reviews/codex-slice7-messaging-auth.md-353-apps/api/app/api/messaging.py:201:
reviews/codex-slice7-messaging-auth.md-354-apps/api/app/api/messaging.py:202:    Section 7: informal chat never becomes authoritative knowledge
reviews/codex-slice7-messaging-auth.md:355:apps/api/app/api/messaging.py:203:    automatically. This route is the explicit human act that the rule
reviews/codex-slice7-messaging-auth.md-356-apps/api/app/api/messaging.py:204:    demands, and it is the only one in this module that writes a
reviews/codex-slice7-messaging-auth.md-357-apps/api/app/api/messaging.py:205:    controlled record -- which is exactly why it is the only one gated.
reviews/codex-slice7-messaging-auth.md-358-apps/api/app/api/messaging.py:206:    """
reviews/codex-slice7-messaging-auth.md-359-apps/api/app/api/messaging.py:207:    try:
--
reviews/codex-slice7-messaging-auth.md-426-apps/api/tests/db/test_023_messaging.py:12:somebody with no access to it. The test below is the one that would have
reviews/codex-slice7-messaging-auth.md-427-apps/api/tests/db/test_023_messaging.py:13:caught it.
reviews/codex-slice7-messaging-auth.md-428-apps/api/tests/db/test_023_messaging.py:14:
reviews/codex-slice7-messaging-auth.md-429-apps/api/tests/db/test_023_messaging.py:15:**Informal chat never becomes authoritative knowledge automatically**
reviews/codex-slice7-messaging-auth.md:430:apps/api/tests/db/test_023_messaging.py:16:(§7). Promotion exists, is explicit, produces a TASK rather than a
reviews/codex-slice7-messaging-auth.md-431-apps/api/tests/db/test_023_messaging.py:17:conclusion, and links back to the message it came from.
reviews/codex-slice7-messaging-auth.md-432-apps/api/tests/db/test_023_messaging.py:18:
reviews/codex-slice7-messaging-auth.md-433-apps/api/tests/db/test_023_messaging.py:19:Everything here runs on `app_session` where the boundary is the subject,
reviews/codex-slice7-messaging-auth.md-434-apps/api/tests/db/test_023_messaging.py:20:because the owner is exempt from RLS while `relforcerowsecurity` is FALSE
--
reviews/codex-slice7-messaging-auth.md-664-apps/api/tests/db/test_023_messaging.py:250:
reviews/codex-slice7-messaging-auth.md-665-apps/api/tests/db/test_023_messaging.py:251:def test_promotion_creates_a_task_and_links_back_to_the_message(
reviews/codex-slice7-messaging-auth.md-666-apps/api/tests/db/test_023_messaging.py:252:    app_session: Session, channel_fixture: dict[str, uuid.UUID]
reviews/codex-slice7-messaging-auth.md-667-apps/api/tests/db/test_023_messaging.py:253:) -> None:
reviews/codex-slice7-messaging-auth.md:668:apps/api/tests/db/test_023_messaging.py:254:    """§7: conclusions become controlled records only by explicit human
reviews/codex-slice7-messaging-auth.md-669-apps/api/tests/db/test_023_messaging.py:255:    promotion -- and what they become is a TASK, not a decision.
reviews/codex-slice7-messaging-auth.md-670-apps/api/tests/db/test_023_messaging.py:256:
reviews/codex-slice7-messaging-auth.md-671-apps/api/tests/db/test_023_messaging.py:257:    The link back is the digital thread's rule applied to conversation:
reviews/codex-slice7-messaging-auth.md-672-apps/api/tests/db/test_023_messaging.py:258:    the task can always answer "where did this come from?".
--
reviews/codex-slice7-messaging-auth.md-691-apps/api/tests/db/test_023_messaging.py:277:        app_session,
reviews/codex-slice7-messaging-auth.md-692-apps/api/tests/db/test_023_messaging.py:278:        message_id=message["id"],
reviews/codex-slice7-messaging-auth.md-693-apps/api/tests/db/test_023_messaging.py:279:        organization_id=fx["org"],
reviews/codex-slice7-messaging-auth.md-694-apps/api/tests/db/test_023_messaging.py:280:        actor_id=fx["author"],
reviews/codex-slice7-messaging-auth.md:695:apps/api/tests/db/test_023_messaging.py:281:        task_type="experiment",
reviews/codex-slice7-messaging-auth.md-696-apps/api/tests/db/test_023_messaging.py:282:        title="Re-run adhesion at 5 C",
reviews/codex-slice7-messaging-auth.md-697-apps/api/tests/db/test_023_messaging.py:283:    )
reviews/codex-slice7-messaging-auth.md-698-apps/api/tests/db/test_023_messaging.py:284:    app_session.commit()
reviews/codex-slice7-messaging-auth.md-699-apps/api/tests/db/test_023_messaging.py:285:
--
reviews/codex-slice7-messaging-auth.md-969-.github/workflows/ci.yml:161:          # container would turn the entire tenancy suite into skips and
reviews/codex-slice7-messaging-auth.md-970-.github/workflows/ci.yml:162:          # the job would still be green. Fail if they did not run.
reviews/codex-slice7-messaging-auth.md-971-.github/workflows/ci.yml:163:          count=$(pytest tests/db -q --collect-only 2>/dev/null | grep -c "test_" || echo 0)
reviews/codex-slice7-messaging-auth.md-972-.github/workflows/ci.yml:164:          if [ "$count" -lt 12 ]; then
reviews/codex-slice7-messaging-auth.md:973:.github/workflows/ci.yml:165:            echo "expected >=12 tenancy tests, collected $count"; exit 1
reviews/codex-slice7-messaging-auth.md-974-.github/workflows/ci.yml:166:          fi
reviews/codex-slice7-messaging-auth.md-975-.github/workflows/ci.yml:167:          pytest tests/db -q --no-header -rs \
reviews/codex-slice7-messaging-auth.md-976-.github/workflows/ci.yml:168:            | tee /tmp/db.txt
reviews/codex-slice7-messaging-auth.md-977-.github/workflows/ci.yml:169:          if grep -q "skipped" /tmp/db.txt; then
--
reviews/codex-slice7-messaging-auth.md-1025-.github/workflows/ci.yml:217:          set -- $counts
reviews/codex-slice7-messaging-auth.md-1026-.github/workflows/ci.yml:218:          materials=$1; suppliers=$2; sds=$3; units=$4
reviews/codex-slice7-messaging-auth.md-1027-.github/workflows/ci.yml:219:          formulas=$5; versions=$6; components=$7
reviews/codex-slice7-messaging-auth.md-1028-.github/workflows/ci.yml:220:
reviews/codex-slice7-messaging-auth.md:1029:.github/workflows/ci.yml:221:          # The expected numbers come from demo-data.json, read here rather
reviews/codex-slice7-messaging-auth.md-1030-.github/workflows/ci.yml:222:          # than hardcoded, so adding a material to the demonstration does
reviews/codex-slice7-messaging-auth.md-1031-.github/workflows/ci.yml:223:          # not silently fail this gate.
reviews/codex-slice7-messaging-auth.md:1032:.github/workflows/ci.yml:224:          expected=$(python - <<'PY'
reviews/codex-slice7-messaging-auth.md-1033-.github/workflows/ci.yml:225:          import json, pathlib
reviews/codex-slice7-messaging-auth.md-1034-.github/workflows/ci.yml:226:          d = json.loads(pathlib.Path("../../apps/web/lib/demo/demo-data.json").read_text(encoding="utf-8"))
reviews/codex-slice7-messaging-auth.md-1035-.github/workflows/ci.yml:227:          versions = [v for f in d["formulas"] for v in f["versions"]]
reviews/codex-slice7-messaging-auth.md-1036-.github/workflows/ci.yml:228:          print(len(d["materials"]), len(d["suppliers"]), len(d["formulas"]),
reviews/codex-slice7-messaging-auth.md-1037-.github/workflows/ci.yml:229:                len(versions), sum(len(v["components"]) for v in versions))
reviews/codex-slice7-messaging-auth.md-1038-.github/workflows/ci.yml:230:          PY
reviews/codex-slice7-messaging-auth.md-1039-.github/workflows/ci.yml:231:          )
reviews/codex-slice7-messaging-auth.md:1040:.github/workflows/ci.yml:232:          set -- $expected
reviews/codex-slice7-messaging-auth.md:1041:.github/workflows/ci.yml:233:          exp_materials=$1; exp_suppliers=$2; exp_formulas=$3
reviews/codex-slice7-messaging-auth.md:1042:.github/workflows/ci.yml:234:          exp_versions=$4; exp_components=$5
reviews/codex-slice7-messaging-auth.md-1043-.github/workflows/ci.yml:235:
reviews/codex-slice7-messaging-auth.md-1044-.github/workflows/ci.yml:236:          fail=0
reviews/codex-slice7-messaging-auth.md-1045-.github/workflows/ci.yml:237:          check() {
reviews/codex-slice7-messaging-auth.md-1046-.github/workflows/ci.yml:238:            if [ "$2" -ne "$3" ]; then
reviews/codex-slice7-messaging-auth.md-1047-.github/workflows/ci.yml:239:              echo "MISMATCH $1: database has $2, demo-data.json has $3"; fail=1
reviews/codex-slice7-messaging-auth.md-1048-.github/workflows/ci.yml:240:            fi
reviews/codex-slice7-messaging-auth.md-1049-.github/workflows/ci.yml:241:          }
reviews/codex-slice7-messaging-auth.md:1050:.github/workflows/ci.yml:242:          check materials  "$materials"  "$exp_materials"
reviews/codex-slice7-messaging-auth.md:1051:.github/workflows/ci.yml:243:          check suppliers  "$suppliers"  "$exp_suppliers"
reviews/codex-slice7-messaging-auth.md:1052:.github/workflows/ci.yml:244:          check formulas   "$formulas"   "$exp_formulas"
reviews/codex-slice7-messaging-auth.md:1053:.github/workflows/ci.yml:245:          check versions   "$versions"   "$exp_versions"
reviews/codex-slice7-messaging-auth.md:1054:.github/workflows/ci.yml:246:          check components "$components" "$exp_components"
reviews/codex-slice7-messaging-auth.md-1055-.github/workflows/ci.yml:247:
reviews/codex-slice7-messaging-auth.md-1056-.github/workflows/ci.yml:248:          # EVERY material must carry an SDS. Without one the formulation
reviews/codex-slice7-messaging-auth.md-1057-.github/workflows/ci.yml:249:          # safety check hard-blocks submission, so a seeded database
reviews/codex-slice7-messaging-auth.md-1058-.github/workflows/ci.yml:250:          # missing them is a demonstration in which no formula can be
reviews/codex-slice7-messaging-auth.md-1059-.github/workflows/ci.yml:251:          # submitted -- the exact deadlock this slice's review found.
reviews/codex-slice7-messaging-auth.md:1060:.github/workflows/ci.yml:252:          check sds "$sds" "$exp_materials"
reviews/codex-slice7-messaging-auth.md-1061-.github/workflows/ci.yml:253:
reviews/codex-slice7-messaging-auth.md-1062-.github/workflows/ci.yml:254:          if [ "$units" -lt 1 ]; then
reviews/codex-slice7-messaging-auth.md-1063-.github/workflows/ci.yml:255:            echo "MISMATCH units: Administration section 3 seeded nothing"; fail=1
reviews/codex-slice7-messaging-auth.md-1064-.github/workflows/ci.yml:256:          fi
--
reviews/codex-slice7-messaging-auth.md-1086-.github/workflows/ci.yml:278:        # BOTH directions -- serving the shell only ever proved that it
reviews/codex-slice7-messaging-auth.md-1087-.github/workflows/ci.yml:279:        # removes items, which a filter returning nothing would also do.
reviews/codex-slice7-messaging-auth.md-1088-.github/workflows/ci.yml:280:        run: npm test
reviews/codex-slice7-messaging-auth.md-1089-.github/workflows/ci.yml:281:      - working-directory: apps/web
reviews/codex-slice7-messaging-auth.md:1090:.github/workflows/ci.yml:282:        # NODE_ENV=production explicitly: building as development ships
reviews/codex-slice7-messaging-auth.md-1091-.github/workflows/ci.yml:283:        # the dev React runtime, which behaves differently from what was
reviews/codex-slice7-messaging-auth.md-1092-.github/workflows/ci.yml:284:        # tested and is slower and larger.
reviews/codex-slice7-messaging-auth.md-1093-.github/workflows/ci.yml:285:        env:
reviews/codex-slice7-messaging-auth.md-1094-.github/workflows/ci.yml:286:          NODE_ENV: production
--
reviews/codex-slice7-messaging-auth.md-1097-.github/workflows/ci.yml:289:      - name: Build the mode the site actually ships in, and assert it
reviews/codex-slice7-messaging-auth.md-1098-.github/workflows/ci.yml:290:        working-directory: apps/web
reviews/codex-slice7-messaging-auth.md-1099-.github/workflows/ci.yml:291:        # CI only ever built `standalone`. The DEPLOYED site is the static
reviews/codex-slice7-messaging-auth.md-1100-.github/workflows/ci.yml:292:        # EXPORT, and the two differ in ways that have already broken the
reviews/codex-slice7-messaging-auth.md:1101:.github/workflows/ci.yml:293:        # front door once: under `output: "export"` a server `redirect()`
reviews/codex-slice7-messaging-auth.md:1102:.github/workflows/ci.yml:294:        # emits an error document, and without `trailingSlash` the export
reviews/codex-slice7-messaging-auth.md-1103-.github/workflows/ci.yml:295:        # writes dashboard.html, which Render 404s because it does no
reviews/codex-slice7-messaging-auth.md-1104-.github/workflows/ci.yml:296:        # clean-URL fallback.
reviews/codex-slice7-messaging-auth.md-1105-.github/workflows/ci.yml:297:        #
reviews/codex-slice7-messaging-auth.md-1106-.github/workflows/ci.yml:298:        # Both guards existed only inside the Render build command — that is,
--
reviews/codex-slice7-messaging-auth.md-1108-.github/workflows/ci.yml:300:        # landed on master. Running them here makes a regression a failed PR
reviews/codex-slice7-messaging-auth.md-1109-.github/workflows/ci.yml:301:        # instead of a broken production front door.
reviews/codex-slice7-messaging-auth.md-1110-.github/workflows/ci.yml:302:        env:
reviews/codex-slice7-messaging-auth.md-1111-.github/workflows/ci.yml:303:          NODE_ENV: production
reviews/codex-slice7-messaging-auth.md:1112:.github/workflows/ci.yml:304:          NEXT_OUTPUT: export
reviews/codex-slice7-messaging-auth.md-1113-.github/workflows/ci.yml:305:        run: |
reviews/codex-slice7-messaging-auth.md-1114-.github/workflows/ci.yml:306:          set -euo pipefail
reviews/codex-slice7-messaging-auth.md-1115-.github/workflows/ci.yml:307:          npm run build
reviews/codex-slice7-messaging-auth.md-1116-.github/workflows/ci.yml:308:          if grep -q "__next_error__" out/index.html; then
reviews/codex-slice7-messaging-auth.md:1117:.github/workflows/ci.yml:309:            echo "::error::/ exported as a Next.js error document — the front door is broken"
reviews/codex-slice7-messaging-auth.md-1118-.github/workflows/ci.yml:310:            exit 1
reviews/codex-slice7-messaging-auth.md-1119-.github/workflows/ci.yml:311:          fi
reviews/codex-slice7-messaging-auth.md-1120-.github/workflows/ci.yml:312:          test -f out/dashboard/index.html || {
reviews/codex-slice7-messaging-auth.md-1121-.github/workflows/ci.yml:313:            echo "::error::out/dashboard/index.html missing — /dashboard would 404 on a host with no .html fallback"
--
reviews/codex-slice7-messaging-auth.md-1123-.github/workflows/ci.yml:315:          }
reviews/codex-slice7-messaging-auth.md-1124-.github/workflows/ci.yml:316:          test -f out/admin/index.html || {
reviews/codex-slice7-messaging-auth.md-1125-.github/workflows/ci.yml:317:            echo "::error::out/admin/index.html missing"; exit 1
reviews/codex-slice7-messaging-auth.md-1126-.github/workflows/ci.yml:318:          }
reviews/codex-slice7-messaging-auth.md:1127:.github/workflows/ci.yml:319:          echo "static export OK: real root document, directory indexes present"
reviews/codex-slice7-messaging-auth.md-1128-.github/workflows/ci.yml:320:
reviews/codex-slice7-messaging-auth.md-1129-.github/workflows/ci.yml:321:  e2e:
reviews/codex-slice7-messaging-auth.md-1130-.github/workflows/ci.yml:322:    name: E2E — browser shell, axe-core, API over HTTP
reviews/codex-slice7-messaging-auth.md-1131-.github/workflows/ci.yml:323:    runs-on: ubuntu-latest
--
reviews/codex-slice7-messaging-auth.md-1261-.github/workflows/ci.yml:453:          scan-type: fs
reviews/codex-slice7-messaging-auth.md-1262-.github/workflows/ci.yml:454:          scan-ref: .
reviews/codex-slice7-messaging-auth.md-1263-.github/workflows/ci.yml:455:          severity: HIGH,CRITICAL
reviews/codex-slice7-messaging-auth.md-1264-.github/workflows/ci.yml:456:          # A high-severity finding blocks the merge. The source is
reviews/codex-slice7-messaging-auth.md:1265:.github/workflows/ci.yml:457:          # explicit that this gates staging deployment.
reviews/codex-slice7-messaging-auth.md-1266-.github/workflows/ci.yml:458:          exit-code: "1"
reviews/codex-slice7-messaging-auth.md-1267-.github/workflows/ci.yml:459:          ignore-unfixed: true
reviews/codex-slice7-messaging-auth.md-1268-.github/workflows/ci.yml:460:
reviews/codex-slice7-messaging-auth.md-1269-.github/workflows/ci.yml:461:      - name: Semgrep
--
reviews/codex-slice7-messaging-auth.md-1445-apps/api/app/domains/messaging/service.py:11:🔴 TWO RULES THAT SHAPE EVERYTHING BELOW
reviews/codex-slice7-messaging-auth.md-1446-apps/api/app/domains/messaging/service.py:12:
reviews/codex-slice7-messaging-auth.md-1447-apps/api/app/domains/messaging/service.py:13:**Informal chat never becomes authoritative knowledge automatically.**
reviews/codex-slice7-messaging-auth.md-1448-apps/api/app/domains/messaging/service.py:14:§7. `promote_message` is the only path from a message to a controlled
reviews/codex-slice7-messaging-auth.md:1449:apps/api/app/domains/messaging/service.py:15:record, it requires an explicit human act, and it creates a TASK rather
reviews/codex-slice7-messaging-auth.md-1450-apps/api/app/domains/messaging/service.py:16:than a conclusion — somebody still has to do the work and sign for it.
reviews/codex-slice7-messaging-auth.md-1451-apps/api/app/domains/messaging/service.py:17:Nothing here promotes anything on its own.
reviews/codex-slice7-messaging-auth.md-1452-apps/api/app/domains/messaging/service.py:18:
reviews/codex-slice7-messaging-auth.md-1453-apps/api/app/domains/messaging/service.py:19:**A notification must not disclose what the recipient cannot see.**
--
reviews/codex-slice7-messaging-auth.md-2091-apps/api/app/domains/messaging/service.py:657:) -> dict[str, Any]:
reviews/codex-slice7-messaging-auth.md-2092-apps/api/app/domains/messaging/service.py:658:    """Turn a message into a controlled record — a TASK.
reviews/codex-slice7-messaging-auth.md-2093-apps/api/app/domains/messaging/service.py:659:
reviews/codex-slice7-messaging-auth.md-2094-apps/api/app/domains/messaging/service.py:660:    🔴 §7: "Informal chat never becomes authoritative knowledge
reviews/codex-slice7-messaging-auth.md:2095:apps/api/app/domains/messaging/service.py:661:    automatically. Conclusions become controlled records only by explicit
reviews/codex-slice7-messaging-auth.md-2096-apps/api/app/domains/messaging/service.py:662:    human promotion."
reviews/codex-slice7-messaging-auth.md-2097-apps/api/app/domains/messaging/service.py:663:
reviews/codex-slice7-messaging-auth.md:2098:apps/api/app/domains/messaging/service.py:664:    This is that explicit act, and it deliberately creates a task rather
reviews/codex-slice7-messaging-auth.md-2099-apps/api/app/domains/messaging/service.py:665:    than a decision or a conclusion: somebody still has to do the work and
reviews/codex-slice7-messaging-auth.md-2100-apps/api/app/domains/messaging/service.py:666:    sign for it. A path from "somebody said so in chat" straight to a
reviews/codex-slice7-messaging-auth.md-2101-apps/api/app/domains/messaging/service.py:667:    technical decision is the thing the rule forbids.
reviews/codex-slice7-messaging-auth.md-2102-apps/api/app/domains/messaging/service.py:668:
--
reviews/codex-slice7-messaging-auth.md-2314-scripts/keycloak-bootstrap.sh:9:# under a different name: "which production path WRITES this?". Importing
reviews/codex-slice7-messaging-auth.md-2315-scripts/keycloak-bootstrap.sh:10:# that realm gives you an identity provider nobody can authenticate
reviews/codex-slice7-messaging-auth.md-2316-scripts/keycloak-bootstrap.sh:11:# against.
reviews/codex-slice7-messaging-auth.md-2317-scripts/keycloak-bootstrap.sh:12:#
reviews/codex-slice7-messaging-auth.md:2318:scripts/keycloak-bootstrap.sh:13:# It also explains why authentication has never once been exercised. The
reviews/codex-slice7-messaging-auth.md:2319:scripts/keycloak-bootstrap.sh:14:# API verifies tokens properly (JWKS, issuer, audience, expiry -- all
reviews/codex-slice7-messaging-auth.md-2320-scripts/keycloak-bootstrap.sh:15:# four), and it has never had a real token to verify, because no Keycloak
reviews/codex-slice7-messaging-auth.md-2321-scripts/keycloak-bootstrap.sh:16:# has ever run anywhere: not on Render, not in CI, not on the dev host.
reviews/codex-slice7-messaging-auth.md-2322-scripts/keycloak-bootstrap.sh:17:#
reviews/codex-slice7-messaging-auth.md-2323-scripts/keycloak-bootstrap.sh:18:# WHAT IT DOES NOT DO
--
reviews/codex-slice7-messaging-auth.md-3157-657-) -> dict[str, Any]:
reviews/codex-slice7-messaging-auth.md-3158-658-    """Turn a message into a controlled record — a TASK.
reviews/codex-slice7-messaging-auth.md-3159-659-
reviews/codex-slice7-messaging-auth.md-3160-660-    🔴 §7: "Informal chat never becomes authoritative knowledge
reviews/codex-slice7-messaging-auth.md:3161:661-    automatically. Conclusions become controlled records only by explicit
reviews/codex-slice7-messaging-auth.md-3162-662-    human promotion."
reviews/codex-slice7-messaging-auth.md-3163-663-
reviews/codex-slice7-messaging-auth.md:3164:664-    This is that explicit act, and it deliberately creates a task rather
reviews/codex-slice7-messaging-auth.md-3165-665-    than a decision or a conclusion: somebody still has to do the work and
reviews/codex-slice7-messaging-auth.md-3166-666-    sign for it. A path from "somebody said so in chat" straight to a
reviews/codex-slice7-messaging-auth.md-3167-667-    technical decision is the thing the rule forbids.
reviews/codex-slice7-messaging-auth.md-3168-668-
--
reviews/codex-slice7-messaging-auth.md-3574-apps/api/app/api/messaging.py-199-) -> dict[str, Any]:
reviews/codex-slice7-messaging-auth.md-3575-apps/api/app/api/messaging.py-200-    """The only route here that requires a permission.
reviews/codex-slice7-messaging-auth.md-3576-apps/api/app/api/messaging.py-201-
reviews/codex-slice7-messaging-auth.md-3577-apps/api/app/api/messaging.py-202-    Section 7: informal chat never becomes authoritative knowledge
reviews/codex-slice7-messaging-auth.md:3578:apps/api/app/api/messaging.py-203-    automatically. This route is the explicit human act that the rule
reviews/codex-slice7-messaging-auth.md-3579-apps/api/app/api/messaging.py-204-    demands, and it is the only one in this module that writes a
reviews/codex-slice7-messaging-auth.md-3580-apps/api/app/api/messaging.py-205-    controlled record -- which is exactly why it is the only one gated.
reviews/codex-slice7-messaging-auth.md-3581-apps/api/app/api/messaging.py-206-    """
reviews/codex-slice7-messaging-auth.md-3582-apps/api/app/api/messaging.py-207-    try:
--
reviews/codex-slice7-messaging-auth.md-3692-.github/workflows/ci.yml-161-          # container would turn the entire tenancy suite into skips and
reviews/codex-slice7-messaging-auth.md-3693-.github/workflows/ci.yml-162-          # the job would still be green. Fail if they did not run.
reviews/codex-slice7-messaging-auth.md-3694-.github/workflows/ci.yml:163:          count=$(pytest tests/db -q --collect-only 2>/dev/null | grep -c "test_" || echo 0)
reviews/codex-slice7-messaging-auth.md-3695-.github/workflows/ci.yml-164-          if [ "$count" -lt 12 ]; then
reviews/codex-slice7-messaging-auth.md:3696:.github/workflows/ci.yml-165-            echo "expected >=12 tenancy tests, collected $count"; exit 1
reviews/codex-slice7-messaging-auth.md-3697-.github/workflows/ci.yml-166-          fi
reviews/codex-slice7-messaging-auth.md-3698-.github/workflows/ci.yml:167:          pytest tests/db -q --no-header -rs \
reviews/codex-slice7-messaging-auth.md-3699-.github/workflows/ci.yml-168-            | tee /tmp/db.txt
reviews/codex-slice7-messaging-auth.md-3700-.github/workflows/ci.yml-169-          if grep -q "skipped" /tmp/db.txt; then
--
reviews/codex-slice7-messaging-auth.md-3757-.github/workflows/ci.yml-453-          scan-type: fs
reviews/codex-slice7-messaging-auth.md-3758-.github/workflows/ci.yml-454-          scan-ref: .
reviews/codex-slice7-messaging-auth.md-3759-.github/workflows/ci.yml-455-          severity: HIGH,CRITICAL
reviews/codex-slice7-messaging-auth.md-3760-.github/workflows/ci.yml-456-          # A high-severity finding blocks the merge. The source is
reviews/codex-slice7-messaging-auth.md:3761:.github/workflows/ci.yml-457-          # explicit that this gates staging deployment.
reviews/codex-slice7-messaging-auth.md-3762-.github/workflows/ci.yml-458-          exit-code: "1"
reviews/codex-slice7-messaging-auth.md-3763-.github/workflows/ci.yml-459-          ignore-unfixed: true
reviews/codex-slice7-messaging-auth.md-3764-.github/workflows/ci.yml-460-
reviews/codex-slice7-messaging-auth.md-3765-.github/workflows/ci.yml-461-      - name: Semgrep
--
reviews/codex-slice7-messaging-auth.md-3943-apps/api/tests/db/test_023_messaging.py-12-somebody with no access to it. The test below is the one that would have
reviews/codex-slice7-messaging-auth.md-3944-apps/api/tests/db/test_023_messaging.py-13-caught it.
reviews/codex-slice7-messaging-auth.md-3945-apps/api/tests/db/test_023_messaging.py-14-
reviews/codex-slice7-messaging-auth.md-3946-apps/api/tests/db/test_023_messaging.py-15-**Informal chat never becomes authoritative knowledge automatically**
reviews/codex-slice7-messaging-auth.md:3947:apps/api/tests/db/test_023_messaging.py-16-(§7). Promotion exists, is explicit, produces a TASK rather than a
reviews/codex-slice7-messaging-auth.md-3948-apps/api/tests/db/test_023_messaging.py-17-conclusion, and links back to the message it came from.
reviews/codex-slice7-messaging-auth.md-3949-apps/api/tests/db/test_023_messaging.py-18-
reviews/codex-slice7-messaging-auth.md-3950-apps/api/tests/db/test_023_messaging.py-19-Everything here runs on `app_session` where the boundary is the subject,
reviews/codex-slice7-messaging-auth.md-3951-apps/api/tests/db/test_023_messaging.py-20-because the owner is exempt from RLS while `relforcerowsecurity` is FALSE
--
reviews/codex-slice7-messaging-auth.md-4181-apps/api/tests/db/test_023_messaging.py-250-
reviews/codex-slice7-messaging-auth.md-4182-apps/api/tests/db/test_023_messaging.py-251-def test_promotion_creates_a_task_and_links_back_to_the_message(
reviews/codex-slice7-messaging-auth.md-4183-apps/api/tests/db/test_023_messaging.py-252-    app_session: Session, channel_fixture: dict[str, uuid.UUID]
reviews/codex-slice7-messaging-auth.md-4184-apps/api/tests/db/test_023_messaging.py-253-) -> None:
reviews/codex-slice7-messaging-auth.md:4185:apps/api/tests/db/test_023_messaging.py-254-    """§7: conclusions become controlled records only by explicit human
reviews/codex-slice7-messaging-auth.md-4186-apps/api/tests/db/test_023_messaging.py-255-    promotion -- and what they become is a TASK, not a decision.
reviews/codex-slice7-messaging-auth.md-4187-apps/api/tests/db/test_023_messaging.py-256-
reviews/codex-slice7-messaging-auth.md-4188-apps/api/tests/db/test_023_messaging.py-257-    The link back is the digital thread's rule applied to conversation:
reviews/codex-slice7-messaging-auth.md-4189-apps/api/tests/db/test_023_messaging.py-258-    the task can always answer "where did this come from?".
--
reviews/codex-slice7-messaging-auth.md-4208-apps/api/tests/db/test_023_messaging.py-277-        app_session,
reviews/codex-slice7-messaging-auth.md-4209-apps/api/tests/db/test_023_messaging.py-278-        message_id=message["id"],
reviews/codex-slice7-messaging-auth.md-4210-apps/api/tests/db/test_023_messaging.py-279-        organization_id=fx["org"],
reviews/codex-slice7-messaging-auth.md-4211-apps/api/tests/db/test_023_messaging.py-280-        actor_id=fx["author"],
reviews/codex-slice7-messaging-auth.md:4212:apps/api/tests/db/test_023_messaging.py-281-        task_type="experiment",
reviews/codex-slice7-messaging-auth.md-4213-apps/api/tests/db/test_023_messaging.py-282-        title="Re-run adhesion at 5 C",
reviews/codex-slice7-messaging-auth.md-4214-apps/api/tests/db/test_023_messaging.py-283-    )
reviews/codex-slice7-messaging-auth.md-4215-apps/api/tests/db/test_023_messaging.py-284-    app_session.commit()
reviews/codex-slice7-messaging-auth.md-4216-apps/api/tests/db/test_023_messaging.py-285-
--
reviews/codex-slice7-messaging-auth.md-4495-- High — [scripts/keycloak-bootstrap.sh:172](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:172): rerunning bootstrap does not repair existing users. `POST /users` returns 409, which `curl` treats as success; the script then uses the existing user without resetting its password, enabling it, or correcting its email. It can exit successfully and write valid subject mappings while those accounts still cannot authenticate with `KC_USER_PASSWORD`.
reviews/codex-slice7-messaging-auth.md-4496-
reviews/codex-slice7-messaging-auth.md-4497-- High — [scripts/keycloak-bootstrap.sh:121](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:121): an existing `evercoat-test` client is also accepted without validation or repair. If it is disabled, lacks direct grants, or lacks the audience mapper, bootstrap reports success but issued tokens are unavailable or rejected by the API. More generally, the `api()` wrapper at line 107 never uses `curl --fail` or checks HTTP status, so failed role-mapping writes at line 210 are silently accepted too.
reviews/codex-slice7-messaging-auth.md-4498-
reviews/codex-slice7-messaging-auth.md:4499:- Medium — [.github/workflows/ci.yml:619](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/.github/workflows/ci.yml:619): `pytest ... || true` discards pytest’s result. The following assertion is documented as checking only that tests passed and none skipped. Therefore a run containing the expected passing test(s) plus a failure/error can still make the auth job green; successful authentication does not prove the complete authentication suite succeeded.
reviews/codex-slice7-messaging-auth.md-4500-
reviews/codex-slice7-messaging-auth.md-4501-Category results:
reviews/codex-slice7-messaging-auth.md-4502-
reviews/codex-slice7-messaging-auth.md:4503:- Restricted-project channel notification/read: none found. `_resolve_mentions` explicitly checks the recipient’s active project membership for restricted projects at service.py:528–565. `list_channels` relies on channel RLS for restricted projects and additionally filters direct channels by membership at service.py:309–330.
reviews/codex-slice7-messaging-auth.md-4504-- Author-session reference disclosure: none found. Resolver lookups are parameterized and execute under the author’s RLS-scoped session; unresolved records generate neither stored links nor identifying errors.
reviews/codex-slice7-messaging-auth.md-4505-- Promotion across inaccessible projects: none found. The source-message/channel lookup remains subject to actor-session RLS.
reviews/codex-slice7-messaging-auth.md-4506-- NULL promotion: no unauthorized task is created, but promoting a direct/announcement channel attempts an insert with `project_id = NULL` at service.py:673–724. If the schema requires a project, the constraint prevents creation and the API returns a 400 containing the raw database error via service.py:725–727. This is poor validation/error hygiene, but not a path that creates a NULL task.
reviews/codex-slice7-messaging-auth.md-4507-- SQL interpolation: none found. SQL values in the reviewed Python files are parameterized; resolver SQL comes only from the static `_RESOLVERS` table.
reviews/codex-slice7-messaging-auth.md:4508:- Credential leakage into logs: none found. Passwords are not explicitly printed, and CI masks generated values. They are passed in command arguments/JSON, but the reviewed scripts do not enable shell tracing.
reviews/codex-slice7-messaging-auth.md:4509:- `keycloak-bind-subs.py`: no SQL-interpolation defect. However, it commits successful bindings before reporting missing users at lines 70–104, so failure leaves a partially rebound database. It exits nonzero, so this is not silent success, but rerunning authentication between remediation steps can produce mixed working/broken accounts.
reviews/codex-slice7-messaging-auth.md-4510-tokens used
reviews/codex-slice7-messaging-auth.md-4511-42,683
reviews/codex-slice7-messaging-auth.md-4512-Found three concrete defects.
reviews/codex-slice7-messaging-auth.md-4513-
reviews/codex-slice7-messaging-auth.md-4514-- High — [scripts/keycloak-bootstrap.sh:172](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:172): rerunning bootstrap does not repair existing users. `POST /users` returns 409, which `curl` treats as success; the script then uses the existing user without resetting its password, enabling it, or correcting its email. It can exit successfully and write valid subject mappings while those accounts still cannot authenticate with `KC_USER_PASSWORD`.
reviews/codex-slice7-messaging-auth.md-4515-
reviews/codex-slice7-messaging-auth.md-4516-- High — [scripts/keycloak-bootstrap.sh:121](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:121): an existing `evercoat-test` client is also accepted without validation or repair. If it is disabled, lacks direct grants, or lacks the audience mapper, bootstrap reports success but issued tokens are unavailable or rejected by the API. More generally, the `api()` wrapper at line 107 never uses `curl --fail` or checks HTTP status, so failed role-mapping writes at line 210 are silently accepted too.
reviews/codex-slice7-messaging-auth.md-4517-
reviews/codex-slice7-messaging-auth.md:4518:- Medium — [.github/workflows/ci.yml:619](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/.github/workflows/ci.yml:619): `pytest ... || true` discards pytest’s result. The following assertion is documented as checking only that tests passed and none skipped. Therefore a run containing the expected passing test(s) plus a failure/error can still make the auth job green; successful authentication does not prove the complete authentication suite succeeded.
reviews/codex-slice7-messaging-auth.md-4519-
reviews/codex-slice7-messaging-auth.md-4520-Category results:
reviews/codex-slice7-messaging-auth.md-4521-
reviews/codex-slice7-messaging-auth.md:4522:- Restricted-project channel notification/read: none found. `_resolve_mentions` explicitly checks the recipient’s active project membership for restricted projects at service.py:528–565. `list_channels` relies on channel RLS for restricted projects and additionally filters direct channels by membership at service.py:309–330.
reviews/codex-slice7-messaging-auth.md-4523-- Author-session reference disclosure: none found. Resolver lookups are parameterized and execute under the author’s RLS-scoped session; unresolved records generate neither stored links nor identifying errors.
reviews/codex-slice7-messaging-auth.md-4524-- Promotion across inaccessible projects: none found. The source-message/channel lookup remains subject to actor-session RLS.
reviews/codex-slice7-messaging-auth.md-4525-- NULL promotion: no unauthorized task is created, but promoting a direct/announcement channel attempts an insert with `project_id = NULL` at service.py:673–724. If the schema requires a project, the constraint prevents creation and the API returns a 400 containing the raw database error via service.py:725–727. This is poor validation/error hygiene, but not a path that creates a NULL task.
reviews/codex-slice7-messaging-auth.md-4526-- SQL interpolation: none found. SQL values in the reviewed Python files are parameterized; resolver SQL comes only from the static `_RESOLVERS` table.
reviews/codex-slice7-messaging-auth.md:4527:- Credential leakage into logs: none found. Passwords are not explicitly printed, and CI masks generated values. They are passed in command arguments/JSON, but the reviewed scripts do not enable shell tracing.
reviews/codex-slice7-messaging-auth.md:4528:- `keycloak-bind-subs.py`: no SQL-interpolation defect. However, it commits successful bindings before reporting missing users at lines 70–104, so failure leaves a partially rebound database. It exits nonzero, so this is not silent success, but rerunning authentication between remediation steps can produce mixed working/broken accounts.
apps/api/app/domains/formulations/service.py:204:    The fix is an INSERT ... SELECT whose source row is the project, with
apps/api/app/domains/formulations/service.py:206:    if the project is not visible-and-writable to this caller the SELECT
apps/api/app/domains/formulations/service.py:224:                SELECT :org, p.id, :code, :name, :family, :description, :owner, :actor
apps/api/app/domains/formulations/service.py:301:def list_formulas(
apps/api/app/domains/formulations/service.py:319:            SELECT f.id, f.formula_code, f.name, f.product_family, f.status,
apps/api/app/domains/formulations/service.py:324:                   (SELECT count(*) FROM formulations.formula_versions v
apps/api/app/domains/formulations/service.py:330:                SELECT v.version_code, v.version_number, v.status
apps/api/app/domains/formulations/service.py:804:                    SELECT id, status, submitted_by, parent_version_id, version_code
apps/api/app/domains/formulations/service.py:936:                    SELECT :org, f.project_id, f.id,
apps/api/app/domains/formulations/service.py:937:                           (SELECT COALESCE(max(v.version_number), 0) + 1
apps/api/app/domains/formulations/service.py:941:                               ((SELECT COALESCE(max(v.version_number), 0) + 1
apps/api/app/domains/formulations/service.py:970:        # Copy the composition. INSERT ... SELECT rather than a read into
apps/api/app/domains/formulations/service.py:989:                    SELECT c.organization_id, c.project_id, :new_vid, c.material_id,
apps/api/app/domains/formulations/service.py:995:                SELECT count(*) FROM copied
apps/api/app/domains/formulations/service.py:1099:                SELECT v.id, v.formula_id, v.project_id, v.organization_id,
apps/api/app/domains/formulations/service.py:1138:            SELECT c.id, c.material_id, c.percentage, c.role_override,
apps/api/app/domains/formulations/service.py:1145:                   (SELECT count(*) FROM materials.material_documents d
apps/api/app/domains/materials/service.py:14:the same statement. A rule checked in a SELECT and enforced in a later
apps/api/app/domains/materials/service.py:425:                    SELECT id, name, category, role, density_g_cm3, cost_per_kg
apps/api/app/domains/materials/service.py:531:    in a SELECT first. A transition validated against a row that another
apps/api/app/domains/materials/service.py:583:                    SELECT id, status, material_code
apps/api/app/domains/materials/service.py:619:                    SELECT status FROM materials.materials
apps/api/app/domains/materials/service.py:662:def list_materials(
apps/api/app/domains/materials/service.py:682:            SELECT m.id, m.material_code, m.name, m.category, m.role, m.status,
apps/api/app/domains/materials/service.py:686:                   (SELECT count(*) FROM materials.material_suppliers ms
apps/api/app/domains/materials/service.py:720:                SELECT id, material_code, name, category, role, status,
apps/api/app/domains/materials/service.py:741:            SELECT ms.id, ms.supplier_id, s.supplier_code, s.name, s.status,
apps/api/app/domains/materials/service.py:780:            SELECT fc.percentage, fc.role_override,
apps/api/app/domains/materials/service.py:885:                    SELECT id, status FROM materials.suppliers
apps/api/app/domains/materials/service.py:920:def list_suppliers(
apps/api/app/domains/materials/service.py:930:            SELECT s.id, s.supplier_code, s.name, s.country, s.status,
apps/api/app/domains/materials/service.py:932:                   (SELECT count(*) FROM materials.material_suppliers ms
apps/api/app/domains/materials/service.py:1105:                SELECT :org, m.id, :dtype, :title, :key,
apps/api/app/domains/materials/service.py:1140:        # INSERT ... SELECT with no source row: the material is not visible
apps/api/app/domains/materials/service.py:1159:def list_material_documents(
apps/api/app/domains/materials/service.py:1171:            SELECT id, document_type, title, storage_key, content_type, byte_size,
apps/api/app/domains/testing/service.py:179:                    SELECT :org, s.project_id, :number, s.id, :method,
apps/api/app/domains/testing/service.py:231:                    SELECT status, sample_number FROM laboratory.samples
apps/api/app/domains/testing/service.py:275:                    SELECT id, execution_status, test_number FROM testing.tests
apps/api/app/domains/testing/service.py:346:        text("SELECT canonical_unit FROM testing.test_methods WHERE id = :m"),
apps/api/app/domains/testing/service.py:698:            SELECT count(*) FROM testing.test_decisions
apps/api/app/domains/testing/service.py:737:                    SELECT id, approval_state, test_number, final_confirmed
apps/api/app/domains/testing/service.py:832:                SELECT id, decision, decision_stage, authority_level, condition_text,
apps/api/app/domains/testing/service.py:845:def list_tests(
apps/api/app/domains/testing/service.py:865:            SELECT t.id, t.test_number, t.project_id, t.execution_status,
apps/api/app/domains/testing/service.py:872:                   (SELECT count(*) FROM testing.test_replicates r
apps/api/app/domains/testing/service.py:910:                SELECT replicates_required, cv_limit, canonical_unit,
apps/api/app/domains/testing/service.py:927:                SELECT id, replicate_number, measured_value, unit, is_excluded,
apps/api/app/domains/testing/service.py:951:                    SELECT target_value, minimum_value, maximum_value,
apps/api/app/domains/testing/service.py:1027:                SELECT id, organization_id, project_id, test_number, sample_id, method_id,
apps/api/app/domains/opportunities/service.py:126:            SELECT 1 FROM innovation.opportunities
apps/api/app/domains/opportunities/service.py:210:    # SELECT.
apps/api/app/domains/opportunities/service.py:259:                SELECT status FROM innovation.opportunities
apps/api/app/domains/opportunities/service.py:342:            SELECT o.status, o.opportunity_code, o.title, o.product_family,
apps/api/app/domains/opportunities/service.py:345:                       SELECT 1 FROM projects.projects p
apps/api/app/domains/opportunities/service.py:368:        text("SELECT 1 FROM projects.projects WHERE project_code = :c AND organization_id = :org"),
apps/api/app/domains/opportunities/service.py:446:def list_opportunities(
apps/api/app/domains/opportunities/service.py:453:            SELECT o.id, o.opportunity_code, o.title, o.product_family,
apps/api/app/domains/opportunities/service.py:490:            SELECT o.*, u.display_name AS created_by_name,
apps/api/app/domains/failures/service.py:151:                    SELECT :org, p.id, :code, :title, :description, :severity,
apps/api/app/domains/failures/service.py:231:                SELECT t.id, t.project_id, t.test_number, t.calculated_result,
apps/api/app/domains/failures/service.py:259:                SELECT id, failure_code, status FROM quality.failures
apps/api/app/domains/failures/service.py:537:                    SELECT possible_cause FROM quality.failure_hypotheses
apps/api/app/domains/failures/service.py:720:                SELECT project_id, version_code FROM formulations.formula_versions
apps/api/app/domains/failures/service.py:806:            SELECT count(*) FROM quality.failure_actions
apps/api/app/domains/failures/service.py:862:def list_failures(
apps/api/app/domains/failures/service.py:873:            SELECT f.id, f.failure_code, f.title, f.severity, f.status, f.project_id,
apps/api/app/domains/failures/service.py:875:                   (SELECT count(*) FROM quality.failure_hypotheses h
apps/api/app/domains/failures/service.py:877:                   (SELECT count(*) FROM quality.failure_hypotheses h
apps/api/app/domains/failures/service.py:880:                   (SELECT count(*) FROM quality.failure_actions a
apps/api/app/domains/failures/service.py:913:                SELECT id, possible_cause, mechanism, confidence, source, origin,
apps/api/app/domains/failures/service.py:930:                SELECT l.hypothesis_id, l.evidence_id, l.relationship, l.note,
apps/api/app/domains/failures/service.py:957:                SELECT id, evidence_type, summary, detail, referenced_entity_type,
apps/api/app/domains/failures/service.py:972:                SELECT id, action_type, description, status, assigned_to, due_date,
apps/api/app/domains/failures/service.py:992:                SELECT id, organization_id, project_id, failure_code, title, description,
apps/api/app/domains/laboratory/service.py:174:                    SELECT :org, v.project_id, v.id, :number,
apps/api/app/domains/laboratory/service.py:210:        # The INSERT ... SELECT matched no version. Say which of the two
apps/api/app/domains/laboratory/service.py:217:                    SELECT status, version_code FROM formulations.formula_versions
apps/api/app/domains/laboratory/service.py:333:            SELECT id, status, batch_number FROM laboratory.batches
apps/api/app/domains/laboratory/service.py:348:            SELECT id, status, batch_number FROM laboratory.batches
apps/api/app/domains/laboratory/service.py:363:            SELECT id, status, batch_number FROM laboratory.batches
apps/api/app/domains/laboratory/service.py:510:                    SELECT status, lot_number FROM materials.material_lots
apps/api/app/domains/laboratory/service.py:610:            SELECT count(*) FROM laboratory.batch_components
apps/api/app/domains/laboratory/service.py:666:                    SELECT id, status, batch_number, executed_by
apps/api/app/domains/laboratory/service.py:915:def list_batches(
apps/api/app/domains/laboratory/service.py:926:            SELECT b.id, b.batch_number, b.status, b.planned_quantity_kg,
apps/api/app/domains/laboratory/service.py:930:                   (SELECT count(*) FROM laboratory.batch_components c
apps/api/app/domains/laboratory/service.py:932:                   (SELECT count(*) FROM laboratory.batch_components c
apps/api/app/domains/laboratory/service.py:935:                   (SELECT count(*) FROM laboratory.batch_deviations d
apps/api/app/domains/laboratory/service.py:937:                   (SELECT count(*) FROM laboratory.samples s
apps/api/app/domains/laboratory/service.py:973:            SELECT c.id, c.material_id, c.planned_mass_kg, c.actual_mass_kg,
apps/api/app/domains/laboratory/service.py:1016:                SELECT id, parameter_code, value, unit, stage, recorded_at, notes
apps/api/app/domains/laboratory/service.py:1030:                SELECT id, description, severity, raised_at, resolution, resolved_at,
apps/api/app/domains/laboratory/service.py:1045:                SELECT id, sample_number, quantity_g, purpose, status, storage_location,
apps/api/app/domains/laboratory/service.py:1065:                SELECT b.id, b.organization_id, b.project_id, b.formula_version_id,
apps/api/app/domains/laboratory/service.py:1094:                SELECT c.material_id, c.percentage, c.display_order,

Repository and API surface are mapped; authentication, authorization, RLS, and sensitive dynamic-permission routes have been traced. Moving to verification and targeted checks.
  ✓ Map the repository and identify API entry points, configuration, and dependencies
  ✓ Trace authentication, authorization, validation, data access, and sensitive operations
  → Run targeted static checks and inspect tests/configuration for security gaps
  • Produce a prioritized security audit with evidence and remediation
2026-08-20T19:14:32.559003Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest apps/api/tests/auth apps/api/tests/test_keycloak_realm.py -q; python -m ruff check apps/api/app --output-format concise'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest apps/api/tests/auth apps/api/tests/test_keycloak_realm.py -q; python -m ruff check apps/api/app --output-format concise' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP\apps\api
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest apps/api/tests/auth apps/api/tests/test_keycloak_realm.py -q; python -m ruff check apps/api/app --output-format concise'` rejected: blocked by policy
2026-08-20T19:14:37.692137Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest tests/auth tests/test_keycloak_realm.py -q'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest tests/auth tests/test_keycloak_realm.py -q' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP\apps\api
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m ruff check app --output-format concise' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP\apps\api
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest tests/auth tests/test_keycloak_realm.py -q'` rejected: blocked by policy
2026-08-20T19:14:37.697171Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m ruff check app --output-format concise'` rejected: blocked by policy
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m ruff check app --output-format concise'` rejected: blocked by policy
codex
The managed read-only sandbox prevents the test and lint runners from starting because they may create caches, so dynamic verification is unavailable in this session. I’ll distinguish that limitation from code findings and finish with source-backed results only.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "rate.?limit|slowapi|limiter|throttl" apps/api/app apps/api/pyproject.toml; rg -n -C 3 "def list_(projects|opportunities|materials|suppliers|formulas|batches|tests|failures)" apps/api/app/domains; rg -n "LIMIT|OFFSET" apps/api/app/domains/projects apps/api/app/domains/opportunities apps/api/app/domains/materials apps/api/app/domains/formulations apps/api/app/domains/laboratory apps/api/app/domains/testing apps/api/app/domains/failures' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 392ms:
apps/api/app/domains\testing\service.py-842-    return test
apps/api/app/domains\testing\service.py-843-
apps/api/app/domains\testing\service.py-844-
apps/api/app/domains\testing\service.py:845:def list_tests(
apps/api/app/domains\testing\service.py-846-    session: Session,
apps/api/app/domains\testing\service.py-847-    *,
apps/api/app/domains\testing\service.py-848-    organization_id: uuid.UUID,
--
apps/api/app/domains\formulations\service.py-298-    }
apps/api/app/domains\formulations\service.py-299-
apps/api/app/domains\formulations\service.py-300-
apps/api/app/domains\formulations\service.py:301:def list_formulas(
apps/api/app/domains\formulations\service.py-302-    session: Session,
apps/api/app/domains\formulations\service.py-303-    *,
apps/api/app/domains\formulations\service.py-304-    organization_id: uuid.UUID,
--
apps/api/app/domains\failures\service.py-859-# ---------------------------------------------------------------------------
apps/api/app/domains\failures\service.py-860-
apps/api/app/domains\failures\service.py-861-
apps/api/app/domains\failures\service.py:862:def list_failures(
apps/api/app/domains\failures\service.py-863-    session: Session,
apps/api/app/domains\failures\service.py-864-    *,
apps/api/app/domains\failures\service.py-865-    organization_id: uuid.UUID,
--
apps/api/app/domains\materials\service.py-659-    return dict(row)
apps/api/app/domains\materials\service.py-660-
apps/api/app/domains\materials\service.py-661-
apps/api/app/domains\materials\service.py:662:def list_materials(
apps/api/app/domains\materials\service.py-663-    session: Session,
apps/api/app/domains\materials\service.py-664-    *,
apps/api/app/domains\materials\service.py-665-    organization_id: uuid.UUID,
--
apps/api/app/domains\materials\service.py-917-    return dict(row)
apps/api/app/domains\materials\service.py-918-
apps/api/app/domains\materials\service.py-919-
apps/api/app/domains\materials\service.py:920:def list_suppliers(
apps/api/app/domains\materials\service.py-921-    session: Session,
apps/api/app/domains\materials\service.py-922-    *,
apps/api/app/domains\materials\service.py-923-    organization_id: uuid.UUID,
--
apps/api/app/domains\laboratory\service.py-912-# ---------------------------------------------------------------------------
apps/api/app/domains\laboratory\service.py-913-
apps/api/app/domains\laboratory\service.py-914-
apps/api/app/domains\laboratory\service.py:915:def list_batches(
apps/api/app/domains\laboratory\service.py-916-    session: Session,
apps/api/app/domains\laboratory\service.py-917-    *,
apps/api/app/domains\laboratory\service.py-918-    organization_id: uuid.UUID,
--
apps/api/app/domains\opportunities\service.py-443-    return project_id
apps/api/app/domains\opportunities\service.py-444-
apps/api/app/domains\opportunities\service.py-445-
apps/api/app/domains\opportunities\service.py:446:def list_opportunities(
apps/api/app/domains\opportunities\service.py-447-    session: Session, *, organization_id: uuid.UUID, status: str | None = None
apps/api/app/domains\opportunities\service.py-448-) -> list[dict[str, Any]]:
apps/api/app/domains\opportunities\service.py-449-    """The innovation funnel, most urgent first."""
apps/api/app/domains/materials\service.py:698:            LIMIT :limit
apps/api/app/domains/materials\service.py:938:            LIMIT :limit
apps/api/app/domains/projects\dashboard.py:174:            LIMIT 10
apps/api/app/domains/projects\dashboard.py:256:            LIMIT 5
apps/api/app/domains/formulations\service.py:334:                LIMIT 1
apps/api/app/domains/formulations\service.py:339:            LIMIT :limit
apps/api/app/domains/failures\service.py:889:            LIMIT :limit
apps/api/app/domains/testing\service.py:883:            LIMIT :limit
apps/api/app/domains/laboratory\service.py:948:            LIMIT :limit

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -A 14 "def list_(materials|suppliers|formulas|batches|tests|failures|opportunities)" apps/api/app/domains; rg -n -A 12 "def list_projects" apps/api/app/domains apps/api/app/api/projects.py; rg -n -A 8 "def list_(materials|suppliers|formulas|batches|tests|failures|opportunities)" apps/api/app/api' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
2026-08-20T19:14:54.473682Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.4 seconds
Output:
apps/api/app/domains\testing\service.py:845:def list_tests(
apps/api/app/domains\testing\service.py-846-    session: Session,
apps/api/app/domains\testing\service.py-847-    *,
apps/api/app/domains\testing\service.py-848-    organization_id: uuid.UUID,
apps/api/app/domains\testing\service.py-849-    project_id: uuid.UUID | None = None,
apps/api/app/domains\testing\service.py-850-    review_state: str | None = None,
apps/api/app/domains\testing\service.py-851-    limit: int = 200,
apps/api/app/domains\testing\service.py-852-) -> list[dict[str, Any]]:
apps/api/app/domains\testing\service.py-853-    """The test queue.
apps/api/app/domains\testing\service.py-854-
apps/api/app/domains\testing\service.py-855-    Deliberately does NOT derive a disposition per row. Doing so would
apps/api/app/domains\testing\service.py-856-    mean a statistics query per test, and a list view that silently costs
apps/api/app/domains\testing\service.py-857-    N round trips is how a queue becomes unusable at fifty rows. The
apps/api/app/domains\testing\service.py-858-    stored axes are returned so a list can show what is waiting; the
apps/api/app/domains\testing\service.py-859-    traffic light belongs to the detail view, where it can be computed
--
apps/api/app/domains\laboratory\service.py:915:def list_batches(
apps/api/app/domains\laboratory\service.py-916-    session: Session,
apps/api/app/domains\laboratory\service.py-917-    *,
apps/api/app/domains\laboratory\service.py-918-    organization_id: uuid.UUID,
apps/api/app/domains\laboratory\service.py-919-    project_id: uuid.UUID | None = None,
apps/api/app/domains\laboratory\service.py-920-    status: str | None = None,
apps/api/app/domains\laboratory\service.py-921-    limit: int = 200,
apps/api/app/domains\laboratory\service.py-922-) -> list[dict[str, Any]]:
apps/api/app/domains\laboratory\service.py-923-    rows = session.execute(
apps/api/app/domains\laboratory\service.py-924-        text(
apps/api/app/domains\laboratory\service.py-925-            """
apps/api/app/domains\laboratory\service.py-926-            SELECT b.id, b.batch_number, b.status, b.planned_quantity_kg,
apps/api/app/domains\laboratory\service.py-927-                   b.tolerance_percent, b.project_id, b.formula_version_id,
apps/api/app/domains\laboratory\service.py-928-                   v.version_code, f.formula_code, f.name AS formula_name,
apps/api/app/domains\laboratory\service.py-929-                   b.started_at, b.completed_at, b.updated_at,
--
apps/api/app/domains\materials\service.py:662:def list_materials(
apps/api/app/domains\materials\service.py-663-    session: Session,
apps/api/app/domains\materials\service.py-664-    *,
apps/api/app/domains\materials\service.py-665-    organization_id: uuid.UUID,
apps/api/app/domains\materials\service.py-666-    status: str | None = None,
apps/api/app/domains\materials\service.py-667-    role: str | None = None,
apps/api/app/domains\materials\service.py-668-    search: str | None = None,
apps/api/app/domains\materials\service.py-669-    limit: int = 200,
apps/api/app/domains\materials\service.py-670-) -> list[dict[str, Any]]:
apps/api/app/domains\materials\service.py-671-    """The material library, newest code first within each status.
apps/api/app/domains\materials\service.py-672-
apps/api/app/domains\materials\service.py-673-    RLS already restricts the rows to this organization. The explicit
apps/api/app/domains\materials\service.py-674-    `organization_id` predicate is not redundant belt-and-braces: it is
apps/api/app/domains\materials\service.py-675-    what makes the query correct when it is called from the Celery worker,
apps/api/app/domains\materials\service.py-676-    whose session sets the GUCs from a job payload rather than from a
--
apps/api/app/domains\materials\service.py:920:def list_suppliers(
apps/api/app/domains\materials\service.py-921-    session: Session,
apps/api/app/domains\materials\service.py-922-    *,
apps/api/app/domains\materials\service.py-923-    organization_id: uuid.UUID,
apps/api/app/domains\materials\service.py-924-    status: str | None = None,
apps/api/app/domains\materials\service.py-925-    limit: int = 200,
apps/api/app/domains\materials\service.py-926-) -> list[dict[str, Any]]:
apps/api/app/domains\materials\service.py-927-    rows = session.execute(
apps/api/app/domains\materials\service.py-928-        text(
apps/api/app/domains\materials\service.py-929-            """
apps/api/app/domains\materials\service.py-930-            SELECT s.id, s.supplier_code, s.name, s.country, s.status,
apps/api/app/domains\materials\service.py-931-                   s.quality_rating, s.contact_name, s.contact_email, s.updated_at,
apps/api/app/domains\materials\service.py-932-                   (SELECT count(*) FROM materials.material_suppliers ms
apps/api/app/domains\materials\service.py-933-                     WHERE ms.supplier_id = s.id) AS material_count
apps/api/app/domains\materials\service.py-934-            FROM materials.suppliers s
--
apps/api/app/domains\opportunities\service.py:446:def list_opportunities(
apps/api/app/domains\opportunities\service.py-447-    session: Session, *, organization_id: uuid.UUID, status: str | None = None
apps/api/app/domains\opportunities\service.py-448-) -> list[dict[str, Any]]:
apps/api/app/domains\opportunities\service.py-449-    """The innovation funnel, most urgent first."""
apps/api/app/domains\opportunities\service.py-450-    rows = session.execute(
apps/api/app/domains\opportunities\service.py-451-        text(
apps/api/app/domains\opportunities\service.py-452-            """
apps/api/app/domains\opportunities\service.py-453-            SELECT o.id, o.opportunity_code, o.title, o.product_family,
apps/api/app/domains\opportunities\service.py-454-                   o.target_application, o.status, o.priority, o.decision,
apps/api/app/domains\opportunities\service.py-455-                   o.decided_at, o.created_at,
apps/api/app/domains\opportunities\service.py-456-                   u.display_name AS created_by_name,
apps/api/app/domains\opportunities\service.py-457-                   p.id AS project_id, p.project_code
apps/api/app/domains\opportunities\service.py-458-            FROM innovation.opportunities o
apps/api/app/domains\opportunities\service.py-459-            JOIN core.users u ON u.id = o.created_by
apps/api/app/domains\opportunities\service.py-460-            LEFT JOIN projects.projects p
--
apps/api/app/domains\formulations\service.py:301:def list_formulas(
apps/api/app/domains\formulations\service.py-302-    session: Session,
apps/api/app/domains\formulations\service.py-303-    *,
apps/api/app/domains\formulations\service.py-304-    organization_id: uuid.UUID,
apps/api/app/domains\formulations\service.py-305-    project_id: uuid.UUID | None = None,
apps/api/app/domains\formulations\service.py-306-    limit: int = 200,
apps/api/app/domains\formulations\service.py-307-) -> list[dict[str, Any]]:
apps/api/app/domains\formulations\service.py-308-    """Formulas visible to this caller, with their latest version.
apps/api/app/domains\formulations\service.py-309-
apps/api/app/domains\formulations\service.py-310-    RLS does the confidentiality filtering: a formula in a restricted
apps/api/app/domains\formulations\service.py-311-    project the caller does not belong to is simply absent. That is why
apps/api/app/domains\formulations\service.py-312-    this returns no count of what was hidden -- a "3 formulas you cannot
apps/api/app/domains\formulations\service.py-313-    see" line would itself disclose the existence of a restricted
apps/api/app/domains\formulations\service.py-314-    project's work.
apps/api/app/domains\formulations\service.py-315-    """
--
apps/api/app/domains\failures\service.py:862:def list_failures(
apps/api/app/domains\failures\service.py-863-    session: Session,
apps/api/app/domains\failures\service.py-864-    *,
apps/api/app/domains\failures\service.py-865-    organization_id: uuid.UUID,
apps/api/app/domains\failures\service.py-866-    project_id: uuid.UUID | None = None,
apps/api/app/domains\failures\service.py-867-    status: str | None = None,
apps/api/app/domains\failures\service.py-868-    limit: int = 200,
apps/api/app/domains\failures\service.py-869-) -> list[dict[str, Any]]:
apps/api/app/domains\failures\service.py-870-    rows = session.execute(
apps/api/app/domains\failures\service.py-871-        text(
apps/api/app/domains\failures\service.py-872-            """
apps/api/app/domains\failures\service.py-873-            SELECT f.id, f.failure_code, f.title, f.severity, f.status, f.project_id,
apps/api/app/domains\failures\service.py-874-                   f.test_id, f.formula_version_id, f.opened_at, f.closed_at,
apps/api/app/domains\failures\service.py-875-                   (SELECT count(*) FROM quality.failure_hypotheses h
apps/api/app/domains\failures\service.py-876-                     WHERE h.failure_id = f.id) AS hypothesis_count,
apps/api/app/api/projects.py:150:def list_projects(
apps/api/app/api/projects.py-151-    principal: Principal = Depends(require_permission("project.view")),
apps/api/app/api/projects.py-152-    session: Session = Depends(get_db),
apps/api/app/api/projects.py-153-) -> list[ProjectSummary]:
apps/api/app/api/projects.py-154-    """Projects the caller may see.
apps/api/app/api/projects.py-155-
apps/api/app/api/projects.py-156-    No organization or confidentiality filter in the SQL: RLS applies
apps/api/app/api/projects.py-157-    both, and a restricted project the caller is not a member of simply
apps/api/app/api/projects.py-158-    does not appear. The application-side check is the resource-scope
apps/api/app/api/projects.py-159-    dependency on the detail routes.
apps/api/app/api/projects.py-160-    """
apps/api/app/api/projects.py-161-    rows = session.execute(
apps/api/app/api/projects.py-162-        text(

 exited 1 in 439ms:
apps/api/app/domains\testing\service.py:845:def list_tests(
apps/api/app/domains\testing\service.py-846-    session: Session,
apps/api/app/domains\testing\service.py-847-    *,
apps/api/app/domains\testing\service.py-848-    organization_id: uuid.UUID,
apps/api/app/domains\testing\service.py-849-    project_id: uuid.UUID | None = None,
apps/api/app/domains\testing\service.py-850-    review_state: str | None = None,
apps/api/app/domains\testing\service.py-851-    limit: int = 200,
apps/api/app/domains\testing\service.py-852-) -> list[dict[str, Any]]:
apps/api/app/domains\testing\service.py-853-    """The test queue.
apps/api/app/domains\testing\service.py-854-
apps/api/app/domains\testing\service.py-855-    Deliberately does NOT derive a disposition per row. Doing so would
apps/api/app/domains\testing\service.py-856-    mean a statistics query per test, and a list view that silently costs
apps/api/app/domains\testing\service.py-857-    N round trips is how a queue becomes unusable at fifty rows. The
apps/api/app/domains\testing\service.py-858-    stored axes are returned so a list can show what is waiting; the
apps/api/app/domains\testing\service.py-859-    traffic light belongs to the detail view, where it can be computed
--
apps/api/app/domains\laboratory\service.py:915:def list_batches(
apps/api/app/domains\laboratory\service.py-916-    session: Session,
apps/api/app/domains\laboratory\service.py-917-    *,
apps/api/app/domains\laboratory\service.py-918-    organization_id: uuid.UUID,
apps/api/app/domains\laboratory\service.py-919-    project_id: uuid.UUID | None = None,
apps/api/app/domains\laboratory\service.py-920-    status: str | None = None,
apps/api/app/domains\laboratory\service.py-921-    limit: int = 200,
apps/api/app/domains\laboratory\service.py-922-) -> list[dict[str, Any]]:
apps/api/app/domains\laboratory\service.py-923-    rows = session.execute(
apps/api/app/domains\laboratory\service.py-924-        text(
apps/api/app/domains\laboratory\service.py-925-            """
apps/api/app/domains\laboratory\service.py-926-            SELECT b.id, b.batch_number, b.status, b.planned_quantity_kg,
apps/api/app/domains\laboratory\service.py-927-                   b.tolerance_percent, b.project_id, b.formula_version_id,
apps/api/app/domains\laboratory\service.py-928-                   v.version_code, f.formula_code, f.name AS formula_name,
apps/api/app/domains\laboratory\service.py-929-                   b.started_at, b.completed_at, b.updated_at,
--
apps/api/app/domains\materials\service.py:662:def list_materials(
apps/api/app/domains\materials\service.py-663-    session: Session,
apps/api/app/domains\materials\service.py-664-    *,
apps/api/app/domains\materials\service.py-665-    organization_id: uuid.UUID,
apps/api/app/domains\materials\service.py-666-    status: str | None = None,
apps/api/app/domains\materials\service.py-667-    role: str | None = None,
apps/api/app/domains\materials\service.py-668-    search: str | None = None,
apps/api/app/domains\materials\service.py-669-    limit: int = 200,
apps/api/app/domains\materials\service.py-670-) -> list[dict[str, Any]]:
apps/api/app/domains\materials\service.py-671-    """The material library, newest code first within each status.
apps/api/app/domains\materials\service.py-672-
apps/api/app/domains\materials\service.py-673-    RLS already restricts the rows to this organization. The explicit
apps/api/app/domains\materials\service.py-674-    `organization_id` predicate is not redundant belt-and-braces: it is
apps/api/app/domains\materials\service.py-675-    what makes the query correct when it is called from the Celery worker,
apps/api/app/domains\materials\service.py-676-    whose session sets the GUCs from a job payload rather than from a
--
apps/api/app/domains\materials\service.py:920:def list_suppliers(
apps/api/app/domains\materials\service.py-921-    session: Session,
apps/api/app/domains\materials\service.py-922-    *,
apps/api/app/domains\materials\service.py-923-    organization_id: uuid.UUID,
apps/api/app/domains\materials\service.py-924-    status: str | None = None,
apps/api/app/domains\materials\service.py-925-    limit: int = 200,
apps/api/app/domains\materials\service.py-926-) -> list[dict[str, Any]]:
apps/api/app/domains\materials\service.py-927-    rows = session.execute(
apps/api/app/domains\materials\service.py-928-        text(
apps/api/app/domains\materials\service.py-929-            """
apps/api/app/domains\materials\service.py-930-            SELECT s.id, s.supplier_code, s.name, s.country, s.status,
apps/api/app/domains\materials\service.py-931-                   s.quality_rating, s.contact_name, s.contact_email, s.updated_at,
apps/api/app/domains\materials\service.py-932-                   (SELECT count(*) FROM materials.material_suppliers ms
apps/api/app/domains\materials\service.py-933-                     WHERE ms.supplier_id = s.id) AS material_count
apps/api/app/domains\materials\service.py-934-            FROM materials.suppliers s
--
apps/api/app/domains\opportunities\service.py:446:def list_opportunities(
apps/api/app/domains\opportunities\service.py-447-    session: Session, *, organization_id: uuid.UUID, status: str | None = None
apps/api/app/domains\opportunities\service.py-448-) -> list[dict[str, Any]]:
apps/api/app/domains\opportunities\service.py-449-    """The innovation funnel, most urgent first."""
apps/api/app/domains\opportunities\service.py-450-    rows = session.execute(
apps/api/app/domains\opportunities\service.py-451-        text(
apps/api/app/domains\opportunities\service.py-452-            """
apps/api/app/domains\opportunities\service.py-453-            SELECT o.id, o.opportunity_code, o.title, o.product_family,
apps/api/app/domains\opportunities\service.py-454-                   o.target_application, o.status, o.priority, o.decision,
apps/api/app/domains\opportunities\service.py-455-                   o.decided_at, o.created_at,
apps/api/app/domains\opportunities\service.py-456-                   u.display_name AS created_by_name,
apps/api/app/domains\opportunities\service.py-457-                   p.id AS project_id, p.project_code
apps/api/app/domains\opportunities\service.py-458-            FROM innovation.opportunities o
apps/api/app/domains\opportunities\service.py-459-            JOIN core.users u ON u.id = o.created_by
apps/api/app/domains\opportunities\service.py-460-            LEFT JOIN projects.projects p
--
apps/api/app/domains\formulations\service.py:301:def list_formulas(
apps/api/app/domains\formulations\service.py-302-    session: Session,
apps/api/app/domains\formulations\service.py-303-    *,
apps/api/app/domains\formulations\service.py-304-    organization_id: uuid.UUID,
apps/api/app/domains\formulations\service.py-305-    project_id: uuid.UUID | None = None,
apps/api/app/domains\formulations\service.py-306-    limit: int = 200,
apps/api/app/domains\formulations\service.py-307-) -> list[dict[str, Any]]:
apps/api/app/domains\formulations\service.py-308-    """Formulas visible to this caller, with their latest version.
apps/api/app/domains\formulations\service.py-309-
apps/api/app/domains\formulations\service.py-310-    RLS does the confidentiality filtering: a formula in a restricted
apps/api/app/domains\formulations\service.py-311-    project the caller does not belong to is simply absent. That is why
apps/api/app/domains\formulations\service.py-312-    this returns no count of what was hidden -- a "3 formulas you cannot
apps/api/app/domains\formulations\service.py-313-    see" line would itself disclose the existence of a restricted
apps/api/app/domains\formulations\service.py-314-    project's work.
apps/api/app/domains\formulations\service.py-315-    """
--
apps/api/app/domains\failures\service.py:862:def list_failures(
apps/api/app/domains\failures\service.py-863-    session: Session,
apps/api/app/domains\failures\service.py-864-    *,
apps/api/app/domains\failures\service.py-865-    organization_id: uuid.UUID,
apps/api/app/domains\failures\service.py-866-    project_id: uuid.UUID | None = None,
apps/api/app/domains\failures\service.py-867-    status: str | None = None,
apps/api/app/domains\failures\service.py-868-    limit: int = 200,
apps/api/app/domains\failures\service.py-869-) -> list[dict[str, Any]]:
apps/api/app/domains\failures\service.py-870-    rows = session.execute(
apps/api/app/domains\failures\service.py-871-        text(
apps/api/app/domains\failures\service.py-872-            """
apps/api/app/domains\failures\service.py-873-            SELECT f.id, f.failure_code, f.title, f.severity, f.status, f.project_id,
apps/api/app/domains\failures\service.py-874-                   f.test_id, f.formula_version_id, f.opened_at, f.closed_at,
apps/api/app/domains\failures\service.py-875-                   (SELECT count(*) FROM quality.failure_hypotheses h
apps/api/app/domains\failures\service.py-876-                     WHERE h.failure_id = f.id) AS hypothesis_count,
apps/api/app/api/projects.py:150:def list_projects(
apps/api/app/api/projects.py-151-    principal: Principal = Depends(require_permission("project.view")),
apps/api/app/api/projects.py-152-    session: Session = Depends(get_db),
apps/api/app/api/projects.py-153-) -> list[ProjectSummary]:
apps/api/app/api/projects.py-154-    """Projects the caller may see.
apps/api/app/api/projects.py-155-
apps/api/app/api/projects.py-156-    No organization or confidentiality filter in the SQL: RLS applies
apps/api/app/api/projects.py-157-    both, and a restricted project the caller is not a member of simply
apps/api/app/api/projects.py-158-    does not appear. The application-side check is the resource-scope
apps/api/app/api/projects.py-159-    dependency on the detail routes.
apps/api/app/api/projects.py-160-    """
apps/api/app/api/projects.py-161-    rows = session.execute(
apps/api/app/api/projects.py-162-        text(

Completed source-backed static audit. Dynamic runners were attempted but blocked by the read-only sandbox, so the final report records that verification limitation explicitly.
  ✓ Map the repository and identify API entry points, configuration, and dependencies
  ✓ Trace authentication, authorization, validation, data access, and sensitive operations
  ✓ Run targeted static checks and inspect tests/configuration for security gaps
  ✓ Produce a prioritized security audit with evidence and remediation
codex
Security audit result: no critical authorization bypass or cross-tenant disclosure was found. The API has strong permission checks and PostgreSQL RLS defenses, but I found four security weaknesses—one high-priority availability issue and three medium-priority hardening gaps.

## Findings

### High — Prometheus label-cardinality denial of service

[main.py:104](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/main.py:104>)  
[main.py:115](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/main.py:115>)  
[main.py:123](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/main.py:123>)

The middleware reads `request.scope["route"]` before `call_next()` performs routing. Consequently, it normally falls back to `request.url.path`. An unauthenticated attacker can request arbitrary unique paths such as `/random/<nonce>`, creating a new Prometheus time series for every value.

This can continuously increase memory use in the API process and monitoring backend until either becomes unavailable.

Remediation:

- Resolve the route template after `call_next()` returns.
- For unmatched routes, use a fixed label such as `"<unmatched>"`, never the raw path.
- Add a regression test sending many unique nonexistent paths and verify they produce one label series.
- Consider restricting `/metrics` to the monitoring network.

### Medium — JWT expiration is verified only when present

[security.py:138](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/core/security.py:138>)  
[security.py:150](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/core/security.py:150>)

`verify_exp=True` validates an `exp` claim when supplied, but the decode configuration does not require the claim to exist. A correctly configured Keycloak normally supplies it, but an issuer/client misconfiguration could produce signed tokens with no expiration that remain valid indefinitely.

Remediation:

```python
options={
    "verify_signature": True,
    "verify_aud": True,
    "verify_iss": True,
    "verify_exp": True,
    "require_exp": True,
    "require_sub": True,
}
```

Also test missing `exp`, missing `sub`, expired tokens, and future `nbf` values.

### Medium — No API rate limiting is implemented

The threat model explicitly requires per-user and per-IP rate limits in [SECURITY.md:115](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/SECURITY.md:115>), but the API contains no limiter or throttling middleware.

Authentication is delegated to Keycloak, but authenticated users can still repeatedly invoke database-heavy list, aggregation, messaging, and mutation endpoints. This raises denial-of-service and message/task spam risks.

Remediation:

- Add Valkey-backed limits per authenticated subject and organization.
- Apply IP-based limits to unauthenticated health and metrics paths.
- Use tighter limits for writes, messaging, search, exports, uploads, and future AI operations.
- Return `429` with `Retry-After`.
- Enforce limits at the reverse proxy as an independent layer.

### Medium — Some collection endpoints execute unbounded queries

The following collections lack pagination or a hard SQL limit:

- Projects: [projects.py:149](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/api/projects.py:149>)
- Opportunities: [opportunities.py:76](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/api/opportunities.py:76>), [service.py:446](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/domains/opportunities/service.py:446>)

Other major collections impose a 200-row service limit, but these return every visible record. Growth—or repeated concurrent requests—can cause excessive database work, memory consumption, and oversized responses.

Remediation:

- Introduce cursor-based pagination with a conservative maximum page size.
- Add stable ordering backed by suitable indexes.
- Return opaque continuation cursors.
- Add load tests for large tenants.

## Positive controls verified

- JWT algorithms are restricted to `RS256`, with signature, audience, and issuer verification.
- Authorization uses database-derived permissions rather than trusting JWT role claims.
- Organization membership is resolved from the database on every request, enabling immediate revocation.
- Tenant and user contexts use transaction-local PostgreSQL settings.
- SQL reviewed was parameterized; no direct SQL-injection path was found.
- Project membership and RLS provide independent resource-scope enforcement.
- Dynamic approval/status permissions are explicitly enforced in the affected routes or services.
- Production API documentation is disabled.
- Production wildcard CORS configuration is rejected.
- Error middleware returns generic responses rather than stack traces.
- Sensitive logging fields are redacted, and request bodies are not logged.
- Major messaging inputs and most domain text fields have explicit size bounds.

## Verification limitation

This was a read-only source audit. I attempted to run the authentication tests and Ruff checks, but the managed read-only sandbox blocked their startup because the tools may create cache files. No repository files were intentionally modified.

Overall risk: **Moderate**. The tenant-isolation and authorization architecture is notably strong; the immediate priority is fixing metrics cardinality, followed by mandatory token lifetime, rate limiting, and pagination.
tokens used
88,678
Security audit result: no critical authorization bypass or cross-tenant disclosure was found. The API has strong permission checks and PostgreSQL RLS defenses, but I found four security weaknesses—one high-priority availability issue and three medium-priority hardening gaps.

## Findings

### High — Prometheus label-cardinality denial of service

[main.py:104](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/main.py:104>)  
[main.py:115](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/main.py:115>)  
[main.py:123](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/main.py:123>)

The middleware reads `request.scope["route"]` before `call_next()` performs routing. Consequently, it normally falls back to `request.url.path`. An unauthenticated attacker can request arbitrary unique paths such as `/random/<nonce>`, creating a new Prometheus time series for every value.

This can continuously increase memory use in the API process and monitoring backend until either becomes unavailable.

Remediation:

- Resolve the route template after `call_next()` returns.
- For unmatched routes, use a fixed label such as `"<unmatched>"`, never the raw path.
- Add a regression test sending many unique nonexistent paths and verify they produce one label series.
- Consider restricting `/metrics` to the monitoring network.

### Medium — JWT expiration is verified only when present

[security.py:138](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/core/security.py:138>)  
[security.py:150](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/core/security.py:150>)

`verify_exp=True` validates an `exp` claim when supplied, but the decode configuration does not require the claim to exist. A correctly configured Keycloak normally supplies it, but an issuer/client misconfiguration could produce signed tokens with no expiration that remain valid indefinitely.

Remediation:

```python
options={
    "verify_signature": True,
    "verify_aud": True,
    "verify_iss": True,
    "verify_exp": True,
    "require_exp": True,
    "require_sub": True,
}
```

Also test missing `exp`, missing `sub`, expired tokens, and future `nbf` values.

### Medium — No API rate limiting is implemented

The threat model explicitly requires per-user and per-IP rate limits in [SECURITY.md:115](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/SECURITY.md:115>), but the API contains no limiter or throttling middleware.

Authentication is delegated to Keycloak, but authenticated users can still repeatedly invoke database-heavy list, aggregation, messaging, and mutation endpoints. This raises denial-of-service and message/task spam risks.

Remediation:

- Add Valkey-backed limits per authenticated subject and organization.
- Apply IP-based limits to unauthenticated health and metrics paths.
- Use tighter limits for writes, messaging, search, exports, uploads, and future AI operations.
- Return `429` with `Retry-After`.
- Enforce limits at the reverse proxy as an independent layer.

### Medium — Some collection endpoints execute unbounded queries

The following collections lack pagination or a hard SQL limit:

- Projects: [projects.py:149](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/api/projects.py:149>)
- Opportunities: [opportunities.py:76](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/api/opportunities.py:76>), [service.py:446](<C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD APP/apps/api/app/domains/opportunities/service.py:446>)

Other major collections impose a 200-row service limit, but these return every visible record. Growth—or repeated concurrent requests—can cause excessive database work, memory consumption, and oversized responses.

Remediation:

- Introduce cursor-based pagination with a conservative maximum page size.
- Add stable ordering backed by suitable indexes.
- Return opaque continuation cursors.
- Add load tests for large tenants.

## Positive controls verified

- JWT algorithms are restricted to `RS256`, with signature, audience, and issuer verification.
- Authorization uses database-derived permissions rather than trusting JWT role claims.
- Organization membership is resolved from the database on every request, enabling immediate revocation.
- Tenant and user contexts use transaction-local PostgreSQL settings.
- SQL reviewed was parameterized; no direct SQL-injection path was found.
- Project membership and RLS provide independent resource-scope enforcement.
- Dynamic approval/status permissions are explicitly enforced in the affected routes or services.
- Production API documentation is disabled.
- Production wildcard CORS configuration is rejected.
- Error middleware returns generic responses rather than stack traces.
- Sensitive logging fields are redacted, and request bodies are not logged.
- Major messaging inputs and most domain text fields have explicit size bounds.

## Verification limitation

This was a read-only source audit. I attempted to run the authentication tests and Ruff checks, but the managed read-only sandbox blocked their startup because the tools may create cache files. No repository files were intentionally modified.

Overall risk: **Moderate**. The tenant-isolation and authorization architecture is notably strong; the immediate priority is fixing metrics cardinality, followed by mandatory token lifetime, rate limiting, and pagination.
