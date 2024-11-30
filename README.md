# Offline folder synchronization utility
## Features
* Content-delta file is calculated based on inventory file .hashes.json containing contains SHA256 file hashes
* Offline synchronization using zipped content-delta file
* Delete absent files is supported
* Final folder state is checked 
* Flexible folder/files excluding (by using sync_filters.py).
	Warning: *.log, *.bak files are ignored by default. Change file_filter function in the sync.py if needed.
* No external dependencies

## How to use

1. Create the inventory file of the remote folder 
	>python sync.py hash <folder> [<use filters (true/false) default true>]
	
 	inventory is created in the .hashes.json file in the folder root

2. Create content-delta file (.zip) for the source folder based on .hashes.json of the remote folder
 	>python sync.py delta <source folder> <inventory file> <content-delta file.zip>

3. Unpack content-delta file into the root of the remote folder. Some files will be replaced. New .hashes.json will be placed in the root.

3a. Optionally check files against .hashes.json without file deletion
	>python sync.py check <folder>

	each file is checked by SHA256 from the .hashes.json

4. Finalize remote folder content
	>python sync.py final <folder>
	
 	some files are deleted
	<br>each file is checked by SHA256 from the .hashes.json
	<br>a file content conflict error may occur (only for the files are not included in the content-delta). Repeat the synchronization scenario.
	
	
