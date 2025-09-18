# TypeDB LocalStack Demo

Sample app that demonstrates how to use TypeDB + LocalStack, to develop and test cloud applications locally.

## Prerequisites

* Docker
* LocalStack Pro (free trial available [here](https://app.localstack.cloud))
* `localstack` CLI
* `terraform` CLI

## Enable the TypeDB Extension

To enable the TypeDB extension in LocalStack, use this command:
```
$ localstack extensions install "git+https://github.com/whummer/localstack-utils.git#egg=localstack-typedb&subdirectory=localstack-typedb"
```

## Start localstack

```
$ localstack start
```

Note: mac users may need to also run
```
$ sudo /Applications/Docker.app/Contents/MacOS/install vmnetd
```

## Deploy and Run the App

To deploy the sample app to LocalStack, run the following `make` target:
```
$ make tf-deploy
```

Once the app is deployed, we can run some HTTP requests against the local API Gateway, which spawns a local Lambda function, and interacts with local TypeDB:
```
$ make requests
```

## License

The code in this repo is available under the Apache 2.0 license.

