# Offline folder content synchronization utility
## Features
* Content-delta file is calculated based on inventory file .hashes.json containing contains sha256 file hashes
* Offline synchronization using zipped content-delta file
* Delete absent files is supported
* Final folder state is checked 
* Flexible folder/files excluding (by using sync_filters.py).
	Warning: *.log, *.bak files are ignored by default. Change file_filter function in the sync.py if needed.
* No external dependencies

## How to use

1. Create inventory of the remote folder 
	python sync.py hash <folder> [<use filters (true/false) default true>]
	inventory is created in the .hashes.json file in the folder root

2. Create content-delta file (?.zip) for the another folder based on .hashes.json of the remote folder
	python sync.py delta <folder> <inventory file> <content-delta file.zip>

3. Unpack <content-delta file.zip> into the root of the remote folder. Some files will be replaced, .hashes.json will be placed in the root

4. Finalize remote folder content
	python sync.py final <folder>
	some files will be deleted
	a file content conflict error may occur (only for the files are not included in the content-delta). Repeat the synchronization scenario.
	
	