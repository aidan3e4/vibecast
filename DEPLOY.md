This service is deployed as a lambda in AWS using a docker container (it was slightly larger to the 250 Mb size limit for the zip file). It's deployed using the aws sam cli. Some commands are in the makefile.

The secrets are stored in AWS secret manager (in aidan3e4 account).

Some other settings such as bucket names are passed through samconfig.toml.