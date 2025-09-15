#!/usr/bin/env python3
"""
Set all COVID-19 DataZone assets to approval not required.
"""

import boto3


def set_covid_assets_no_approval():
    domain_id = "<DOMAIN_ID>"
    project_id = "d8ipo2t2p8oalj"
    region = "us-east-1"

    datazone = boto3.client("datazone", region_name=region)

    print(f"🔍 Finding COVID-19 assets in project...")

    # Search for assets containing "covid" in the name
    try:
        response = datazone.search(
            domainIdentifier=domain_id,
            owningProjectIdentifier=project_id,
            searchScope="ASSET",
            searchText="covid",
            maxResults=50,
        )

        assets = response.get("items", [])
        print(f"📋 Found {len(assets)} assets matching 'covid'")

        covid_assets = []

        for asset in assets:
            asset_id = asset.get("assetItem", {}).get("identifier")
            asset_name = asset.get("assetItem", {}).get("name", "Unknown")
            asset_type = asset.get("assetItem", {}).get("typeName", "Unknown")

            # Check if it's a COVID-19 related asset
            if "covid" in asset_name.lower():
                covid_assets.append(
                    {"id": asset_id, "name": asset_name, "type": asset_type}
                )
                print(f"  - {asset_name} ({asset_type}) - {asset_id}")

        if not covid_assets:
            print("❌ No COVID-19 assets found")
            return

        # Update each asset to set approval not required
        updated_count = 0

        for asset in covid_assets:
            asset_id = asset["id"]
            asset_name = asset["name"]

            try:
                # Get current asset details
                asset_response = datazone.get_asset(
                    domainIdentifier=domain_id, identifier=asset_id
                )

                # Find and update the SubscriptionTermsForm
                forms_output = asset_response.get("formsOutput", [])
                updated_forms = []

                for form in forms_output:
                    if form.get("formName") == "SubscriptionTermsForm":
                        # Update approval required to NO
                        updated_form = {
                            "formName": form["formName"],
                            "content": '{"approvalRequired":"NO"}',
                            "typeIdentifier": form["typeName"],
                            "typeRevision": form["typeRevision"],
                        }
                        updated_forms.append(updated_form)
                        print(
                            f"  📝 Updated SubscriptionTermsForm: approvalRequired = NO"
                        )
                    else:
                        # Keep other forms as-is
                        updated_forms.append(
                            {
                                "formName": form["formName"],
                                "content": form["content"],
                                "typeIdentifier": form["typeName"],
                                "typeRevision": form["typeRevision"],
                            }
                        )

                # Create new asset revision with updated forms
                datazone.create_asset_revision(
                    domainIdentifier=domain_id,
                    identifier=asset_id,
                    name=asset_response["name"],
                    typeRevision=asset_response["typeRevision"],
                    formsInput=updated_forms,
                )

                print(f"✅ Updated {asset_name} - approval not required")
                updated_count += 1

            except Exception as e:
                print(f"❌ Error updating {asset_name}: {e}")
                continue

        print(f"\n🎉 Successfully updated {updated_count} COVID-19 assets")
        print(f"📋 All COVID-19 assets now set to approval not required")

    except Exception as e:
        print(f"❌ Error searching for assets: {e}")


if __name__ == "__main__":
    set_covid_assets_no_approval()
