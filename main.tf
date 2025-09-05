
# Create deployment package for Lambda
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "build/lambda"
  output_path = "build/lambda.zip"
}

# IAM role for Lambda function
resource "aws_iam_role" "lambda_role" {
  name = "snowflake-counter-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Lambda function
resource "aws_lambda_function" "user_lambda" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "user-service"
  role            = aws_iam_role.lambda_role.arn
  handler         = "handler.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.11"
  timeout         = 30
}

# API Gateway
resource "aws_api_gateway_rest_api" "user_api" {
  name        = "user-service-api"
  description = "User Service API"
  tags = {
    _custom_id_ = "users-api"
  }
}

# API Gateway resource 'create'
resource "aws_api_gateway_resource" "user_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_rest_api.user_api.root_resource_id
  path_part   = "users"
}

# API Gateway method 'create'
resource "aws_api_gateway_method" "create_user_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.user_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway integration 'create'
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.user_resource.id
  http_method = aws_api_gateway_method.create_user_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# API Gateway method 'list'
resource "aws_api_gateway_method" "list_users_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.user_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway integration 'list'
resource "aws_api_gateway_integration" "lambda_list_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.user_resource.id
  http_method = aws_api_gateway_method.list_users_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.user_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.user_api.execution_arn}/*/*"
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "user_api_deployment" {
  depends_on = [
    aws_api_gateway_integration.lambda_integration,
  ]

  rest_api_id = aws_api_gateway_rest_api.user_api.id

  lifecycle {
    create_before_destroy = true
  }
}

# Stage
resource "aws_api_gateway_stage" "stage" {
  deployment_id = aws_api_gateway_deployment.user_api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  stage_name    = "test"
}

# Output the API Gateway ID
output "api_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/users"
  description = "API Gateway ID"
}
