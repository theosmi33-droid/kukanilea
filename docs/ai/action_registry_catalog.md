# Action Registry Catalog

Total actions: **261**

## Actions per tool

| Tool | Actions |
|---|---:|
| `filesystem_list` | 29 |
| `generate_zugferd_xml` | 29 |
| `lexoffice_upload` | 29 |
| `mail_generate` | 29 |
| `memory_search` | 29 |
| `memory_store` | 29 |
| `mesh_sync` | 29 |
| `message_to_work_item` | 29 |
| `retrieve_corrections` | 29 |

## Action list

| Action | Critical | Permissions | Audit fields |
|---|---|---|---|
| `CORE.GENERIC.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `CORE.GENERIC.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `CORE.GENERIC.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.LEXOFFICE.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EINSTELLUNGEN.MESH.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `EMAILPOSTFACH.MAIL.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.SEARCH.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `KNOWLEDGE.STORE.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.CORRECTIONS.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.FILESYSTEM.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.ARCHIVE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.AUDIT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.AUTHORIZE` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.CANCEL` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.CREATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.DELETE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.DRY_RUN` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.EXECUTE` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.EXECUTE_ASYNC` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.EXECUTE_BATCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.EXPORT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.FETCH_STATUS` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.GET_BY_ID` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.IMPORT` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.LIST` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.LIST_RECENT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.NORMALIZE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.NOTIFY` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.PLAN` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.PREVIEW` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.READ` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.RESTORE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.RETRY` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.ROLLBACK` | yes | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.SEARCH` | no | tenant:read | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.SEND` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.UPDATE` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.UPLOAD` | no | tenant:read, write | tenant_id, user_id, trace_id |
| `UPLOAD.ZUGFERD.VALIDATE_INPUT` | no | tenant:read | tenant_id, user_id, trace_id |
