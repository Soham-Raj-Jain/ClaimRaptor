from pathlib import Path

from pypdf import PdfReader, PdfWriter


SOURCE_DIR = Path("data/real_world")
OUTPUT_DIR = Path("data/real_world_clean")

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


PACKETS = [
    {
        "source": (
            SOURCE_DIR
            / "nationwide_chrysler_fire_claim.pdf"
        ),

        "output": (
            OUTPUT_DIR
            / "nationwide_chrysler_fire_notice.pdf"
        ),

        # Public source packet contains many unrelated
        # insurance records.
        #
        # NDI page 10 is the relevant Nationwide
        # Chrysler fire-loss notice.
        #
        # pypdf uses zero-based page numbers.
        "pages": [
            9
        ],
    },

    {
        "source": (
            SOURCE_DIR
            / "nationwide_kia_fire_claim.pdf"
        ),

        "output": (
            OUTPUT_DIR
            / "nationwide_kia_fire_notice.pdf"
        ),

        # Page 1 contains the actual Nationwide
        # fire-loss claim notice.
        "pages": [
            0
        ],
    },

    {
        "source": (
            SOURCE_DIR
            / "progressive_vehicle_valuation.pdf"
        ),

        "output": (
            OUTPUT_DIR
            / "progressive_fire_claim_packet.pdf"
        ),

        # Pages:
        # 1-2 = Progressive subrogation notice
        # 5-8 = vehicle damage estimate + totals
        #
        # Zero-based:
        "pages": [
            0,
            1,
            4,
            5,
            6,
            7,
        ],
    },
]


def extract_pages(
    source_path,
    output_path,
    page_indices,
):

    if not source_path.exists():

        print(
            f"SKIP: missing "
            f"{source_path}"
        )

        return

    reader = PdfReader(
        str(source_path)
    )

    writer = PdfWriter()

    print(
        f"\nSource: {source_path}"
    )

    print(
        f"Pages available: "
        f"{len(reader.pages)}"
    )

    added = 0

    for page_index in page_indices:

        if page_index >= len(
            reader.pages
        ):

            print(
                f"WARNING: page "
                f"{page_index + 1} "
                f"does not exist."
            )

            continue

        writer.add_page(
            reader.pages[
                page_index
            ]
        )

        added += 1

        print(
            f"Added page "
            f"{page_index + 1}"
        )

    if added == 0:

        print(
            "No pages extracted."
        )

        return

    with open(
        output_path,
        "wb",
    ) as file:

        writer.write(
            file
        )

    print(
        f"Created: "
        f"{output_path}"
    )

    print(
        f"Output pages: "
        f"{added}"
    )


def main():

    print(
        "Preparing clean "
        "real-world ClaimRaptor packets..."
    )

    for packet in PACKETS:

        extract_pages(
            packet[
                "source"
            ],

            packet[
                "output"
            ],

            packet[
                "pages"
            ],
        )

    print(
        "\nDone."
    )


if __name__ == "__main__":
    main()