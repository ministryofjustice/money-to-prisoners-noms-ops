# money-to-prisoners-prisoner-location-admin
Prisoner Location Admin front-end for Money To Prisoners

## Working with the code

### Run the tests

#### Integration/functional tests

Feature tests are run using a combination of [Cucumber.js](https://github.com/cucumber/cucumber-js)
and [WebdriverIO](http://webdriver.io/api.html).

Feature files are in `test/features/` and step definitions live in `test/features/steps/`.
The WebdriverIO [testrunner](http://webdriver.io/guide/testrunner/gettingstarted.html)
is used to run the tests using a [standalone selenium server](https://www.npmjs.com/package/selenium-standalone).

Config for the testrunner lives in `test/`.

To run the tests against all currently selected browsers (Chrome, Firefox, PhantomJS), run:
```
$ npm test
```

To run the tests headlessly, run:
```
$ npm run test-headless
```

You can also [tag](https://github.com/cucumber/cucumber/wiki/Tags) scenarios with `@wip`
and run the following command to only run those scenarios:
```
$ npm run test-wip
```

### Validate code style

#### Python

In a terminal `cd` into the directory you checked this project out into, then:

```
$ make lint
```

To check for a [specific class of style
violation](http://flake8.readthedocs.org/en/latest/warnings.html), run:

```
$ make lint LINT_OPTS="--select [lint-rules]"
```

#### JavaScript

To lint javascript files using [JSHint](http://jshint.com/), run:
```
$ gulp lint
```

### Run a development Server

In a terminal `cd` into the directory you checked this project out into, then

```
$ make run
```

Wait while Docker does its stuff and you'll soon see something like:
```
djangogulpserve_1 | [BS] Now you can access your site through the following addresses:
djangogulpserve_1 | [BS] Local URL: http://localhost:3000
```

You should be able to point your browser at
[http://localhost:3000](http://localhost:3000) if you're using
*boot2docker* then it'll be at the IP of the boot2docker virtual
machine. You can find it by typing `boot2docker ip` in a terminal. Then
visit http://**boot2docker ip**:3000/

### Log in to the application

Make sure you have a version of the [API](https://github.com/ministryofjustice/money-to-prisoners-api) server
running on port 8000.

You should be able to log into the cash book app using following credentials:

- *test_prison_1 / test_prison_1* for Prison 1
- *test_prison_2 / test_prison_2* for Prison 2
