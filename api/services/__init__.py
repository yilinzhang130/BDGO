"""
Report services registry.

Adding a new report:
    1. Create services/reports/my_report.py subclassing ReportService
    2. Import and register here in REPORT_SERVICES
    3. REST endpoint + Chat tool + frontend card all pick it up.
"""

from services.report_builder import ReportService
from services.reports.buyer_profile import BuyerProfileService
from services.reports.clinical_guidelines import ClinicalGuidelinesService
from services.reports.commercial_assessment import CommercialAssessmentService
from services.reports.dd_checklist import DDChecklistService
from services.reports.deal_evaluator import DealEvaluatorService
from services.reports.deal_teaser import DealTeaserService
from services.reports.disease_landscape import DiseaseLandscapeService
from services.reports.ip_landscape import IPLandscapeService
from services.reports.paper_analysis import PaperAnalysisService
from services.reports.rnpv_valuation import RNPVValuationService
from services.reports.target_radar import TargetRadarService

REPORT_SERVICES: dict[str, ReportService] = {
    PaperAnalysisService.slug: PaperAnalysisService(),
    BuyerProfileService.slug: BuyerProfileService(),
    ClinicalGuidelinesService.slug: ClinicalGuidelinesService(),
    CommercialAssessmentService.slug: CommercialAssessmentService(),
    DDChecklistService.slug: DDChecklistService(),
    DealEvaluatorService.slug: DealEvaluatorService(),
    DealTeaserService.slug: DealTeaserService(),
    DiseaseLandscapeService.slug: DiseaseLandscapeService(),
    IPLandscapeService.slug: IPLandscapeService(),
    RNPVValuationService.slug: RNPVValuationService(),
    TargetRadarService.slug: TargetRadarService(),
}


def get_service(slug: str) -> ReportService | None:
    return REPORT_SERVICES.get(slug)


def list_services() -> list[ReportService]:
    return list(REPORT_SERVICES.values())
