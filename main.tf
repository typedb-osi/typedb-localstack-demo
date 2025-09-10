
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

# API Gateway resource 'users'
resource "aws_api_gateway_resource" "user_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_rest_api.user_api.root_resource_id
  path_part   = "users"
}

# API Gateway resource 'user groups' (nested under users)
resource "aws_api_gateway_resource" "user_groups_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_rest_api.user_api.root_resource_id
  path_part   = "users"
}

resource "aws_api_gateway_resource" "user_groups_nested_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.user_groups_resource.id
  path_part   = "{username}"
}

resource "aws_api_gateway_resource" "user_groups_final_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.user_groups_nested_resource.id
  path_part   = "groups"
}

resource "aws_api_gateway_resource" "user_all_groups_final_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.user_groups_nested_resource.id
  path_part   = "all-groups"
}

# API Gateway resource 'groups'
resource "aws_api_gateway_resource" "group_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_rest_api.user_api.root_resource_id
  path_part   = "groups"
}

# API Gateway resource 'group members' (nested under groups)
resource "aws_api_gateway_resource" "group_members_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.group_resource.id
  path_part   = "{group_name}"
}

resource "aws_api_gateway_resource" "group_members_nested_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.group_members_resource.id
  path_part   = "members"
}

resource "aws_api_gateway_resource" "group_all_members_nested_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.group_members_resource.id
  path_part   = "all-members"
}

resource "aws_api_gateway_resource" "group_groups_nested_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.group_members_resource.id
  path_part   = "groups"
}

resource "aws_api_gateway_resource" "group_all_groups_nested_resource" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  parent_id   = aws_api_gateway_resource.group_members_resource.id
  path_part   = "all-groups"
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

# API Gateway method 'create group'
resource "aws_api_gateway_method" "create_group_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway integration 'create group'
resource "aws_api_gateway_integration" "lambda_create_group_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_resource.id
  http_method = aws_api_gateway_method.create_group_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# API Gateway method 'list groups'
resource "aws_api_gateway_method" "list_groups_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway integration 'list groups'
resource "aws_api_gateway_integration" "lambda_list_groups_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_resource.id
  http_method = aws_api_gateway_method.list_groups_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# API Gateway method 'add member to group'
resource "aws_api_gateway_method" "add_group_member_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_members_nested_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway integration 'add member to group'
resource "aws_api_gateway_integration" "lambda_add_group_member_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_members_nested_resource.id
  http_method = aws_api_gateway_method.add_group_member_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# API Gateway method 'list group members'
resource "aws_api_gateway_method" "list_group_members_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_members_nested_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway integration 'list group members'
resource "aws_api_gateway_integration" "lambda_list_group_members_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_members_nested_resource.id
  http_method = aws_api_gateway_method.list_group_members_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# API Gateway method 'list all group members'
resource "aws_api_gateway_method" "list_all_group_members_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_all_members_nested_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway integration 'list all group members'
resource "aws_api_gateway_integration" "lambda_list_all_group_members_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_all_members_nested_resource.id
  http_method = aws_api_gateway_method.list_all_group_members_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# User Groups Methods and Integrations
resource "aws_api_gateway_method" "list_user_groups_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.user_groups_final_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_list_user_groups_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.user_groups_final_resource.id
  http_method = aws_api_gateway_method.list_user_groups_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

resource "aws_api_gateway_method" "list_all_user_groups_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.user_all_groups_final_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_list_all_user_groups_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.user_all_groups_final_resource.id
  http_method = aws_api_gateway_method.list_all_user_groups_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

# Group Groups Methods and Integrations
resource "aws_api_gateway_method" "list_group_groups_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_groups_nested_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_list_group_groups_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_groups_nested_resource.id
  http_method = aws_api_gateway_method.list_group_groups_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.user_lambda.invoke_arn
}

resource "aws_api_gateway_method" "list_all_group_groups_method" {
  rest_api_id   = aws_api_gateway_rest_api.user_api.id
  resource_id   = aws_api_gateway_resource.group_all_groups_nested_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_list_all_group_groups_integration" {
  rest_api_id = aws_api_gateway_rest_api.user_api.id
  resource_id = aws_api_gateway_resource.group_all_groups_nested_resource.id
  http_method = aws_api_gateway_method.list_all_group_groups_method.http_method

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
    aws_api_gateway_integration.lambda_list_integration,
    aws_api_gateway_integration.lambda_create_group_integration,
    aws_api_gateway_integration.lambda_list_groups_integration,
    aws_api_gateway_integration.lambda_add_group_member_integration,
    aws_api_gateway_integration.lambda_list_group_members_integration,
    aws_api_gateway_integration.lambda_list_all_group_members_integration,
    aws_api_gateway_integration.lambda_list_user_groups_integration,
    aws_api_gateway_integration.lambda_list_all_user_groups_integration,
    aws_api_gateway_integration.lambda_list_group_groups_integration,
    aws_api_gateway_integration.lambda_list_all_group_groups_integration,
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

# Output the API Gateway endpoints
output "api_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test"
  description = "API Gateway base URL"
}

output "users_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/users"
  description = "Users API endpoint"
}

output "groups_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/groups"
  description = "Groups API endpoint"
}

output "group_members_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/groups/{group_name}/members"
  description = "Group members API endpoint (replace {group_name} with actual group name)"
}

output "group_all_members_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/groups/{group_name}/all-members"
  description = "Group all members API endpoint (replace {group_name} with actual group name)"
}

output "user_groups_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/users/{username}/groups"
  description = "User groups API endpoint (replace {username} with actual username)"
}

output "user_all_groups_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/users/{username}/all-groups"
  description = "User all groups API endpoint (replace {username} with actual username)"
}

output "group_groups_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/groups/{group_name}/groups"
  description = "Group groups API endpoint (replace {group_name} with actual group name)"
}

output "group_all_groups_endpoint" {
  value = "http://${aws_api_gateway_rest_api.user_api.id}.execute-api.localhost.localstack.cloud:4566/test/groups/{group_name}/all-groups"
  description = "Group all groups API endpoint (replace {group_name} with actual group name)"
}
