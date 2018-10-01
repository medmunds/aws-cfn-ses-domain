BUILD_DIR = build

build: build.zip


build.zip:	index.py Pipfile  ## Deployable AWS Lambda package
	rm -rf ${BUILD_DIR} build.zip
	mkdir -p ${BUILD_DIR}
	pipenv lock -r > ${BUILD_DIR}/requirements.txt
	pipenv run pip install --no-deps -t ${BUILD_DIR}/ \
		-r ${BUILD_DIR}/requirements.txt
	cp -p -v index.py ${BUILD_DIR}/
	(cd ${BUILD_DIR}; zip -r -9 ../build.zip .)


deploy:	build.zip  ## Upload build to AWS Lambda
	aws lambda update-function-code \
		--function-name cfn-ses-domain \
		--zip-file fileb://build.zip


initial_deploy: build.zip  ## Upload build to AWS Lambda (first time only)
	aws lambda create-function \
		--function-name cfn-ses-domain \
		--zip-file fileb://build.zip \
		--role arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-cfn-ses-domain  \
		--handler index.lambda_handler \
		--runtime python3.6 \
		--timeout 30 \
		--memory-size 128


test:
	pipenv run python -m unittest discover --start-directory tests --top-level-directory .


lint:
	pipenv run cfn-lint *.cf.yaml
