"""Load AdyraForge's real services and projects.

Only L'Atelier de Gastronomie is client work; every other project is a concept
(kind=concept) and is never presented as a client. Copy comes from the v1 site
(adyraforge.netlify.app) and the projects' own live pages. Nothing is invented:
no result metrics, client names or testimonials are seeded. Fill those in
through the admin once confirmed.

Idempotent: existing rows (matched by slug) are left untouched so admin edits
survive a re-run. Pass --force to reset seeded fields to these values.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.portfolio.models import Project, Service, Technology

TECHNOLOGIES: list[tuple[str, str, str]] = [
    ("HTML5", "html5", Technology.Category.FRONTEND),
    ("CSS3", "css3", Technology.Category.FRONTEND),
    ("JavaScript", "javascript", Technology.Category.FRONTEND),
    ("React", "react", Technology.Category.FRONTEND),
    ("Tailwind CSS", "tailwind-css", Technology.Category.FRONTEND),
    ("Node.js", "nodejs", Technology.Category.BACKEND),
    ("Django", "django", Technology.Category.BACKEND),
    ("Python", "python", Technology.Category.BACKEND),
    ("Netlify", "netlify", Technology.Category.DEVOPS),
]

SERVICES: list[dict[str, Any]] = [
    {
        "slug": "websites",
        "name": "Websites",
        "summary": (
            "Complete multi-page platforms designed to represent your brand, scale with "
            "traffic, and establish trust."
        ),
        "description": (
            "Optimized for search accessibility and structural stability: custom "
            "architectural layouts, a robust SEO foundation and integrated responsive designs."
        ),
        "includes": [
            "Custom architectural layouts",
            "Robust SEO foundation",
            "Integrated responsive designs",
        ],
        "order": 1,
    },
    {
        "slug": "landing-pages",
        "name": "Landing Pages",
        "summary": "High-converting single-page campaigns built with surgical focus.",
        "description": (
            "Fast-loading, responsive, and specifically structured to convert traffic into "
            "pipeline prospects: high-performance load times, a conversion-optimized flow and "
            "structured calls to action."
        ),
        "includes": [
            "High-performance load times",
            "Conversion-optimized flow",
            "Structured calls to action",
        ],
        "order": 2,
    },
    {
        "slug": "web-applications",
        "name": "Web Applications",
        "summary": "Custom systems and dashboard applications built with React, Node, and Python.",
        "description": (
            "Designed to run your operations and manage user interactions securely: reactive "
            "state systems, secure API integrations and performance that scales."
        ),
        "includes": [
            "Reactive state systems",
            "Secure API integrations",
            "Optimized performance scaling",
        ],
        "order": 3,
    },
]

PROJECTS: list[dict[str, Any]] = [
    {
        "slug": "latelier-de-gastronomie",
        "kind": Project.Kind.CLIENT,
        "title": "L'Atelier de Gastronomie",
        "industry": "Restaurant / fine dining",
        # Its old URL (phenomenal-belekoy-881bf4.netlify.app) returned Netlify's 404
        # page on 2026-10-13, so it is not advertised as live. Restore with the new URL.
        "status": Project.Status.NOT_LIVE,
        "live_url": "",
        "summary": "A premium responsive website built for fine dining establishments.",
        "solution": (
            "A premium responsive website built for fine dining establishments. Features "
            "dynamic menus, custom layout structures, optimized media presentation, and custom "
            "script integrations for interactive bookings and map location details."
        ),
        "technologies": ["html5", "css3", "javascript", "netlify"],
        "services": ["websites"],
        "is_featured": True,
        "published": True,
        "order": 1,
    },
    {
        "slug": "medicare-plus",
        "kind": Project.Kind.CONCEPT,
        "title": "MediCare Plus",
        "industry": "Healthcare / hospital",
        "status": Project.Status.LIVE,
        "live_url": "https://multimedicareplus.netlify.app/",
        "summary": "Website for a multi-specialty hospital, with online appointment booking.",
        "solution": (
            "A website for a premier multi-specialty hospital presenting its care and "
            "technology, with online appointment booking."
        ),
        "technologies": ["netlify"],
        "services": ["websites"],
        "is_featured": True,
        "published": True,
        "order": 2,
    },
    {
        "slug": "mentality-landing-page",
        "kind": Project.Kind.CONCEPT,
        "title": "mėntality landing page",
        "industry": "",
        "status": Project.Status.LIVE,
        "live_url": "https://forgementality.netlify.app/",
        "summary": "",
        "solution": "",
        "technologies": ["netlify"],
        "services": ["landing-pages"],
        "is_featured": False,
        # Unpublished until its case-study copy is written.
        "published": False,
        "order": 3,
    },
    {
        "slug": "nexus-operations-dashboard",
        "kind": Project.Kind.CONCEPT,
        "title": "Nexus Operations Dashboard",
        "industry": "Enterprise operations",
        "status": Project.Status.NOT_LIVE,
        "live_url": "",
        "summary": "A layout concept for enterprise resource scheduling and operations logging.",
        "solution": (
            "A complex layout concept designed for enterprise resource scheduling and "
            "operations logging. Designed to present rich data formats and responsive controls."
        ),
        "technologies": ["react", "nodejs", "django"],
        "services": ["web-applications"],
        "is_featured": False,
        "published": True,
        "order": 4,
    },
    {
        "slug": "aether-product-launch",
        "kind": Project.Kind.CONCEPT,
        "title": "Aether Product Launch",
        "industry": "Consumer hardware",
        "status": Project.Status.NOT_LIVE,
        "live_url": "",
        "summary": "A single-page marketing concept focusing on hardware releases.",
        "solution": (
            "A single-page marketing concept focusing on hardware releases. Prominently "
            "displays custom interactive sections and newsletter waitlist interfaces."
        ),
        "technologies": ["html5", "tailwind-css", "javascript"],
        "services": ["landing-pages"],
        "is_featured": False,
        "published": True,
        "order": 5,
    },
]

M2M_KEYS = ("technologies", "services")


class Command(BaseCommand):
    help = "Load AdyraForge's real services and projects (idempotent)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing seeded rows with the values in this command.",
        )

    @transaction.atomic
    def handle(self, *args: Any, force: bool = False, **options: Any) -> None:
        counts = {"created": 0, "updated": 0, "skipped": 0}

        techs = {}
        for name, slug, category in TECHNOLOGIES:
            techs[slug], _ = Technology.objects.get_or_create(
                slug=slug, defaults={"name": name, "category": category}
            )

        services = {}
        for data in SERVICES:
            obj, outcome = self._upsert(Service, {**data, "published": True}, force)
            services[obj.slug] = obj
            counts[outcome] += 1

        for data in PROJECTS:
            fields = {k: v for k, v in data.items() if k not in M2M_KEYS}
            project, outcome = self._upsert(Project, fields, force)
            counts[outcome] += 1
            if outcome != "skipped":
                project.full_clean()
                project.technologies.set([techs[s] for s in data["technologies"]])
                project.services.set([services[s] for s in data["services"]])

        self.stdout.write(
            self.style.SUCCESS(
                "seed_portfolio: {created} created, {updated} updated, "
                "{skipped} unchanged (existing; use --force to overwrite)".format(**counts)
            )
        )

    @staticmethod
    def _upsert(model: Any, data: dict[str, Any], force: bool) -> tuple[Any, str]:
        slug = data["slug"]
        existing = model.objects.filter(slug=slug).first()
        if existing is None:
            return model.objects.create(**data), "created"
        if not force:
            return existing, "skipped"
        for key, value in data.items():
            setattr(existing, key, value)
        existing.save()
        return existing, "updated"
