# patch_alias.py
# Adds PLANE_WAYPOINT and PLANE_PATH back into 15.1.0 alias.xml
# so that the 14_11_0 Avatar.def can be used for method ordering

alias_path = r'D:\MMR\venv\Lib\site-packages\replay_unpack\clients\wows\versions\15_1_0\scripts\entity_defs\alias.xml'

insert = """
        <PLANE_WAYPOINT>
                FIXED_DICT
                <Properties>
                        <position><Type>VECTOR3</Type></position>
                        <yaw><Type>FLOAT</Type></yaw>
                        <pitch><Type>INT8</Type></pitch>
                        <time><Type>INT16</Type></time>
                        <type><Type>INT8</Type></type>
                </Properties>
        </PLANE_WAYPOINT>
        <PLANE_PATH>
                ARRAY <of> PLANE_WAYPOINT </of>
        </PLANE_PATH>
"""

with open(alias_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

if 'PLANE_PATH' in content:
    print('PLANE_PATH already present, no changes needed')
else:
    content = content.replace('</root>', insert + '</root>')
    with open(alias_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done - alias.xml patched successfully')
