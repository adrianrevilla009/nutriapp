# infra/terraform/modules/ecr/main.tf
#
# One ECR repository per named image (a NutriApp service's own app image,
# or a shared platform utility image like infra/k8s/images/db-provision).
# Environment-agnostic, per .claude/skills/terraform-conventions/SKILL.md —
# environments/dev/ calls this once per image name it needs.

resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE" # tags are git SHAs (containerization SKILL.md) — never re-pushed

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.kms_key_id
  }

  tags = var.tags
}

# Expire untagged images (failed/superseded builds) after a short window —
# tagged (git-SHA) images are kept indefinitely, since a running
# Deployment's image tag must always remain pullable/traceable.
resource "aws_ecr_lifecycle_policy" "untagged_expiry" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 14 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = { type = "expire" }
      }
    ]
  })
}
