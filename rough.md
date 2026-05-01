i want to design the layout of the app as in, what it is going to have. I want to have a config variable in which there would be set the locationof the manifest folder. 

in the manifest folder there would be a folder named scripts/ and then the registry. 




so the flow is 
when a script is uploaded, some values are going to be uploaded with it as well, like the input variables the config variables and stuff, so in the registry folder for each of the script there is going to be a json. now 


explaining you the flow along with how we have designed to add the scripts.


when you click on add script and tafter you select the .py file, the py file is going to be copied to the scripts folder in the manifest ... being renamed with a uuid, and along with it, another file with a uuid .. another json file with uuid is going to be created in the registry folder, that json is going to have these details.

the structure of the json is going to be like, 
name - (the name of the script that has been given ... with the browse .py file only ... above that add a field, called name this is going to store a string)
then the uuid of the script (using this uuid only we would find them...)
description - (would be option but they would be asked for a small description for this)
input_variables - (the input variables that would be entered during the adding of the script would be kept here), this is going to be a list of dict
config_variable - (this would keep all the config variables that would be ccreated at the time of creation of the script), again list of dict 

output variable -- same list of dict,
then 
dependencies (for now keep this empty)
then
created_at -> a datetime stamp
lastrun_time -> a datetime stamp, empty if never run
lastupdated_datetime_stamp -> 
success_rate -> this logic i am going to include later, just empty for now
help_file_path -> logic later for now only empty string field
current_version -> version 1 if added a new script
previous versions -> here this is going to be a dict, key value, .. here version number along with the uuid of the that version script is going to be there.


can you do this 1, and how can you do this only.







now there is going to be a each script page. 

for this you are going to understand this properly the fields we are having in thee registry of it that is going to be enough to understand what i have been trying to make in this each script page.

{
  "name": "Non_Tcs_New_Metadata_Hidden",
  "uuid": "6d6a8205229844789ba0b1e9c58ae76e",
  "description": "Creates the answersheet excel with the hidden fields, and all.",
  "input_variables": [
    {
      "name": "MAIN_FOLDER",
      "type": "Directory"
    }
  ],
  "config_variable": [],
  "output_variable": [
    {
      "name": "OUTPUT_FOLDER",
      "type": "Directory"
    }
  ],
  "dependencies": [
    "openpyxl",
    "pandas"
  ],
  "created_at": "2026-04-24T09:53:02+00:00",
  "lastrun_time": "",
  "lastupdated_datetime_stamp": "2026-04-24T09:53:02+00:00",
  "success_rate": "",
  "help_file_path": "",
  "current_version": 1,
  "previous_versions": {}
}

these are the things being saved for each of the scripts now there is one thing help_file_path  this is also going to be asked during the adding of the script only. but this is going to be optional.
and the previous versions one... i want everytime a script is added, this previous version is going to be made like a dictionary and the version to be added, like after the adding of the script only it would be saving 1 : "uuid_of_the_script_file"

a key value pair like that, everytime a script gets added. 


now the second thing, there is going to be a each script page. in the each script page there is going to be the details of each script that is required, one button si going to be there for updating the script, and then the details and then there has to be a button to view the script and the entire script would be printed and shown here. and all the config variables the input variables and the output variables are going to be shown in that only. can you make this ..and keep a button view in the each script card... and in the each script page there would be the button run and there is a very big logic for the running only that i would cover later on. 































































































now i want to set the running of the script. 
For running of the script, i want that there to be a sandbox kind of (in a separate thread, i dont want the app to stop while one script, is running, it should be something like there is a parallel process running with the app) 
Now what i want that in the sand box initially there would be a check that would run for the dependencies required for the app to run, if the given dependecies are there, ... then we would proceed to ask for the value of the input variable and the config variable.

if the dependencies are not there, then an uv command would run to add those dependencies to the environment (yes i would like to use uv cause i want to keep the process timing less and uv is blazing fast that pip. thus i would use uv)

finally i would execute the script ... but before executing i want to have all the the variables setup.l 

I just took the name of the input variable while adding the script, but the real reason i took it at that time is for now to have the values. 
with the input variable (if any) then there should be a file i am going to select of that file type, 
suppose input variable is there.. named "main_file" and it is going to have path to a file with .xlsx extension.
i want that before running in a instance, i would like to have a a file selector open up next to the variable value and then i would select a .xlsx file and the script would be then executed upon that file.
similarly with thee output variable, if they have something related to these things, then these are going to be configured.


after that finally inside the sandbox the script would be executed. 


make this possible.

























































there is a serios change in the structure of managing the script,
i want to add, for managing the scripts, the person should be able to manage the scripts in the folder based structures. 


like the script tab is going to have a folder like structure. 






and i dont know how to store it, it would be best if i store it in the given folder 

in the script folder i want to store 

in the manifest only there would be one thing called directory.json.

in that the hierarchy of the folders and the scripts in it would be kept.

so for example we can have folders and the scripts inside it as a list of dictionary.

figure out how this can be done and immpllement it. 