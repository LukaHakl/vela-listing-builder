"""Video-to-listing mapping by photo timestamp proximity."""

from __future__ import annotations

from builders.video_map import (
    AMBIGUITY_WINDOW, diagnose_empty_folder, map_videos, nearest_photo_distance,
    summary, write_review_file,
)


# ===========================================================================
# Video mapping by timestamp proximity
# ===========================================================================

def test_distance_is_to_the_nearest_photo():
    assert nearest_photo_distance(100.0, [50.0, 105.0, 500.0]) == 5.0


def test_a_listing_with_no_photos_is_infinitely_far():
    assert nearest_photo_distance(100.0, []) == float("inf")


def test_a_video_maps_to_the_listing_shot_nearest_in_time():
    matches = map_videos({"clip.mp4": 1000.0},
                         {"SKU-A": [990.0], "SKU-B": [50000.0]})
    assert matches[0].sku == "SKU-A" and not matches[0].ambiguous


def test_two_listings_within_the_window_are_ambiguous_not_guessed():
    """A wrong video is a product page showing a different product, and
    nobody checks."""
    matches = map_videos({"clip.mp4": 1000.0},
                         {"SKU-A": [990.0], "SKU-B": [1010.0]})
    assert matches[0].ambiguous and matches[0].sku == ""
    assert len(matches[0].candidates) == 2


def test_a_clear_winner_outside_the_window_is_assigned():
    matches = map_videos({"clip.mp4": 1000.0},
                         {"SKU-A": [990.0],
                          "SKU-B": [1000.0 + AMBIGUITY_WINDOW * 3]})
    assert matches[0].sku == "SKU-A"


def test_a_video_far_from_everything_is_unmatched():
    """Same-day is not the signal; nearness within the day is."""
    matches = map_videos({"clip.mp4": 0.0}, {"SKU-A": [10 * 3600.0]})
    assert matches[0].unmatched and matches[0].sku == ""


def test_no_listings_leaves_every_video_unmatched():
    assert map_videos({"clip.mp4": 1.0}, {})[0].unmatched


def test_the_review_file_lists_candidates_for_ambiguous_videos(tmp_path):
    path = tmp_path / "review.txt"
    matches = map_videos({"clip.mp4": 1000.0},
                         {"SKU-A": [990.0], "SKU-B": [1010.0]})
    assert write_review_file(matches, str(path)) == 1
    text = path.read_text(encoding="utf-8")
    assert "SKU-A" in text and "SKU-B" in text and "clip.mp4" in text


def test_the_review_file_says_so_when_everything_mapped(tmp_path):
    path = tmp_path / "review.txt"
    matches = map_videos({"clip.mp4": 1000.0}, {"SKU-A": [990.0]})
    assert write_review_file(matches, str(path)) == 0
    assert "exactly one" in path.read_text(encoding="utf-8")


def test_the_summary_separates_mapped_ambiguous_and_unmatched():
    matches = map_videos(
        {"a.mp4": 1000.0, "b.mp4": 2000.0, "c.mp4": 900000.0},
        {"SKU-A": [990.0], "SKU-B": [2010.0], "SKU-C": [2015.0]})
    text = summary(matches)
    assert "videos:     3" in text and "unmatched:  1" in text


# ---------------------------------------------------------------------------
# The Google Drive folder-query trap
# ---------------------------------------------------------------------------

def test_a_visible_folder_returning_nothing_gets_the_real_diagnosis():
    """Not 'no files found' -- parentId queries return empty for folders owned
    by an external account even when sharedWithMe shows them."""
    text = diagnose_empty_folder(folder_visible=True, result_count=0)
    assert "parentId" in text and "Viewer" in text
    assert "Retrying the query will not help" in text


def test_a_folder_with_results_needs_no_diagnosis():
    assert diagnose_empty_folder(folder_visible=True, result_count=5) is None


def test_an_invisible_folder_is_an_ordinary_problem():
    assert diagnose_empty_folder(folder_visible=False, result_count=0) is None
