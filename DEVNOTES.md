# Overview

Goal is to gather information about a set of NIH grants listed in the collection.yaml file. Information flow will be:

config file -> get core project ids
core project ids -> fetch records from NIH reporter
nih reporter records -> have pmids of associated publications
use assoc pubmed ids -> europepmc to get pub records
use assoc pubmed ids -> icite records for each pub record

Store all data as jsonlines, keeping association back to core project identifiers.


# Configuration

Configuration will be in yaml format.

```yaml
# example
# Core project identifiers refer to NIH project ids from NIH reporter
core_project_identifiers:
  u54od036472:
```

# Data collectors

## NIH reporter

Using the NIH reporter ids in the config file.

Documentation is here: https://api.reporter.nih.gov/

In this case, we will use the NIH core project ids to build download the records for each core project id.

## Pubmed

Using the publication information from the nih reporter, use the europepmc API to
gather pubmed records for each grant-associated publication.

API documentation is here: https://europepmc.org/RestfulWebService

## icite

Using the icite API to gather icite records for grant-associated publications.

API documentation is here: https://support.icite.nih.gov/hc/en-us/articles/9513563045787-Bulk-Data-and-API
