"""
Terraform file generation using Jinja2 templates.
"""
import os
import logging
import re
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)


class TerraformGenerator:
    """Generates Terraform files from templates."""

    def __init__(self, templates_dir: str = None):
        """
        Initialize the Terraform generator.

        Args:
            templates_dir: Directory containing Jinja2 templates
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        
        self.templates_dir = Path(templates_dir)
        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        logger.info(f"Initialized Terraform generator with templates from: {self.templates_dir}")


    def generate_bigquery_dataset(
        self,
        dataset_name: str,
        location: str,
        labels: Dict[str, str],
        service_account: str,
    ) -> str:
        """
        Generate Terraform configuration for a BigQuery dataset.

        Args:
            dataset_name: Dataset identifier
            location: GCP region
            labels: Key-value labels
            service_account: Service account email

        Returns:
            Generated Terraform configuration as string
        """
        try:
            # Auto-sanitize dataset name: convert to lowercase and replace spaces/hyphens with underscores
            dataset_name = dataset_name.lower().replace(" ", "_").replace("-", "_")
            
            # Validate dataset name format (after sanitization)
            if not re.match(r"^[a-z0-9_]+$", dataset_name):
                raise ValueError(
                    f"Invalid dataset name after sanitization: {dataset_name}. "
                    f"Must contain only lowercase letters, numbers, and underscores."
                )

            # Load template
            template = self.env.get_template("bigquery_dataset.tf.j2")

            # Render template
            terraform_content = template.render(
                dataset_name=dataset_name,
                location=location,
                labels=labels,
                service_account=service_account,
            )

            logger.info(f"Generated Terraform configuration for dataset: {dataset_name}")
            return terraform_content

        except Exception as e:
            logger.error(f"Error generating Terraform: {e}", exc_info=True)
            raise


    def write_to_file(
        self,
        content: str,
        target_dir: Path,
        filename: str
    ) -> Path:
        """
        Write Terraform content to a file.

        Args:
            content: Terraform configuration content
            target_dir: Target directory (repository path)
            filename: Output filename

        Returns:
            Path to the created file
        """
        try:
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path = target_dir / filename
            file_path.write_text(content)

            logger.info(f"Written Terraform file to: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error writing Terraform file: {e}", exc_info=True)
            raise

    @staticmethod
    def _validate_dataset_name(name: str) -> bool:
        """
        Validate BigQuery dataset name.
        Must contain only lowercase letters, numbers, and underscores.
        """
        pattern = r'^[a-z0-9_]+$'
        return bool(re.match(pattern, name))

    @staticmethod
    def get_relative_path(dataset_name: str, base_dir: str = "datasets") -> str:
        """
        Get the relative path for the Terraform file within the repository.

        Args:
            dataset_name: Dataset name
            base_dir: Base directory (default: datasets)

        Returns:
            Relative path like "datasets/dataset_name.tf"
        """
        return f"{base_dir}/{dataset_name}.tf"
