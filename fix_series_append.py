import json
import os


def fix_series_append_error(notebook_path):
    """Fix the Series append error in a Jupyter notebook by replacing append with pd.concat."""
    print(f"Processing {notebook_path}...")

    # Read the notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    # Track if we made any changes
    changes_made = False

    # Process each cell
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])

            # Replace train.append with pd.concat
            if 'train.append(' in source:
                # Find the line with train.append
                for i, line in enumerate(cell['source']):
                    if 'train.append(' in line:
                        # Extract the argument to append
                        arg = line[line.find(
                            'train.append(') + 12:line.rfind(')')]
                        # Replace with pd.concat
                        cell['source'][i] = line.replace(
                            f'train.append({arg})', f'pd.concat([train, {arg}])')
                        changes_made = True
                        print(
                            f"  Fixed Series append in cell {notebook['cells'].index(cell)}, line {i+1}")

    # Write the updated notebook if changes were made
    if changes_made:
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1)
        print(f"  Saved changes to {notebook_path}")
    else:
        print(f"  No Series append errors found in {notebook_path}")


# Fix the notebook
notebook_path = 'src/analysis/analysis_kelp_2.ipynb'
if os.path.exists(notebook_path):
    fix_series_append_error(notebook_path)
else:
    print(f"Notebook not found: {notebook_path}")

print("Done!")
