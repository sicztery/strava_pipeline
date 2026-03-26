resource "aws_security_group" "webhook_alb" {
  count  = var.enable_webhook_service ? 1 : 0
  name   = "${local.name}-webhook-alb-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "webhook" {
  count  = var.enable_webhook_service ? 1 : 0
  name   = "${local.name}-webhook-sg"
  vpc_id = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group_rule" "webhook_ingress" {
  count                    = var.enable_webhook_service ? 1 : 0
  type                     = "ingress"
  from_port                = var.webhook_container_port
  to_port                  = var.webhook_container_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.webhook[0].id
  source_security_group_id = aws_security_group.webhook_alb[0].id
}

resource "aws_lb" "webhook" {
  count              = var.enable_webhook_service ? 1 : 0
  name               = "${local.name}-webhook-alb"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.webhook_alb[0].id]
  subnets            = var.public_subnet_ids
  tags               = local.tags
}

resource "aws_lb_target_group" "webhook" {
  count       = var.enable_webhook_service ? 1 : 0
  name        = "${local.name}-webhook-tg"
  port        = var.webhook_container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/healthz"
    matcher             = "200-399"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = local.tags
}

resource "aws_lb_listener" "webhook_http" {
  count             = var.enable_webhook_service && var.webhook_certificate_arn == "" ? 1 : 0
  load_balancer_arn = aws_lb.webhook[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.webhook[0].arn
  }
}

resource "aws_lb_listener" "webhook_https" {
  count             = var.enable_webhook_service && var.webhook_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.webhook[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = var.webhook_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.webhook[0].arn
  }
}

resource "aws_lb_listener" "webhook_http_redirect" {
  count             = var.enable_webhook_service && var.webhook_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.webhook[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_ecs_task_definition" "webhook" {
  count                    = var.enable_webhook_service ? 1 : 0
  family                   = "${local.name}-webhook"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.worker.arn

  container_definitions = jsonencode([
    {
      name      = "webhook"
      image     = local.container_image
      essential = true
      command   = ["webhook"]
      portMappings = [
        {
          containerPort = var.webhook_container_port
          hostPort      = var.webhook_container_port
          protocol      = "tcp"
        }
      ]
      environment = [
        for k, v in local.webhook_env : {
          name  = k
          value = v
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.webhook[0].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_service" "webhook" {
  count           = var.enable_webhook_service ? 1 : 0
  name            = "${local.name}-webhook"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.webhook[0].arn
  desired_count   = var.webhook_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.webhook[0].id]
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.webhook[0].arn
    container_name   = "webhook"
    container_port   = var.webhook_container_port
  }

  depends_on = [
    aws_lb_listener.webhook_http,
    aws_lb_listener.webhook_https,
    aws_lb_listener.webhook_http_redirect
  ]

  tags = local.tags
}

resource "aws_ecs_task_definition" "create_subscription" {
  family                   = "${local.name}-create-subscription"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.worker.arn

  container_definitions = jsonencode([
    {
      name      = "create-subscription"
      image     = local.container_image
      essential = true
      command   = ["create_sub"]
      environment = [
        for k, v in local.create_subscription_env : {
          name  = k
          value = v
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}
