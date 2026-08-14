# file-management Specification

## Purpose

Creates NEW documents and opens files/folders (RF-9). Never overwrites, edits, or deletes existing files. Executor is an in-process module (RNF-5).

## Requirements

### Requirement: Create new document (RF-9)

`create_doc` MUST create a new Markdown/text document in the active project (or given path). It MUST refuse to overwrite, edit, or delete an existing file.

#### Scenario: New file

- GIVEN the user says "Jarvis, creá un documento con el resumen del sprint"
- WHEN executed
- THEN a new file MUST be created with the requested content
- AND no existing file MUST be modified

#### Scenario: Overwrite refused

- GIVEN the target file already exists
- WHEN `create_doc` is requested for the same name
- THEN the system MUST refuse and suggest an alternative name
- AND the existing file content MUST remain unchanged

#### Scenario: Invalid path

- GIVEN the target path is invalid
- WHEN `create_doc` is executed
- THEN the system MUST report a spoken error
- AND MUST create nothing

### Requirement: Open file/folder (RF-9)

`open_file_dir` MUST open the requested file or folder with the system file manager (xdg-open) without modifying it.

#### Scenario: Open folder

- GIVEN the user says "Jarvis, abrí la carpeta del proyecto"
- WHEN executed
- THEN the file manager MUST open the active project folder
- AND no file MUST be modified
