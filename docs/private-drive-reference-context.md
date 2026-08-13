# Private Google Drive reference context

The public-source article generators can optionally use two private Google Drive folders as runtime-only editorial background.

## Repository variables

Configure these GitHub Actions repository variables without committing the folder IDs to the repository:

- `GOOGLE_DRIVE_INTERNAL_REFERENCE_FOLDER_ID`: internal operational materials used to improve practical HDN commentary.
- `GOOGLE_DRIVE_LHUB_ARCHIVE_FOLDER_ID`: historical LHub article archive used for topic consistency and duplicate avoidance.

The existing `GOOGLE_SERVICE_ACCOUNT_JSON` Actions secret is reused for read-only Drive/Docs access. Both folders must be shared with that service account.

## Privacy boundary

- Folder IDs, document IDs, Drive URLs, document titles, and raw Drive bodies are not persisted to GitHub state.
- The generator selects only a small number of relevant Google Docs at runtime.
- Contact details, commercial amounts, credentials, and Drive links are sanitized before the text is sent as editorial context.
- The model is instructed never to cite or identify the private source and never to publish client, patient, contract, or operational identifiers.
- If Drive access is unavailable, public-source article generation continues without private context.
- Generated articles remain `draft: true` and require human review before publication.
