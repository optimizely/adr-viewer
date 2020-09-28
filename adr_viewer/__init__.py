import glob
import os
import urlparse

from bottle import Bottle, run
from bs4 import BeautifulSoup
import click
from jinja2 import Environment, PackageLoader, select_autoescape
import mistune


def extract_statuses_from_adr(page_object):
    status_section = page_object.find('h2', text='Status')

    if status_section and status_section.nextSibling:
        current_node = status_section.nextSibling

        while current_node.name != 'h2' and current_node.nextSibling:
            current_node = current_node.nextSibling

            if current_node.name == 'p':
                yield current_node.text
            else:
                continue


def parse_adr_to_config(path):
    adr_as_html = mistune.markdown(open(path).read())

    soup = BeautifulSoup(adr_as_html, features='html.parser')

    status = list(extract_statuses_from_adr(soup))

    if any([line.startswith("Amended by") for line in status]):
        status = 'amended'
    elif any([line.startswith("Accepted") for line in status]):
        status = 'accepted'
    elif any([line.startswith("Superceded by") for line in status]):
        status = 'superceded'
    elif any([line.startswith("Pending") for line in status]):
        status = 'pending'
    elif any([line.startswith("Rejected") for line in status]):
        status = 'rejected'
    else:
        status = 'unknown'

    header = soup.find('h1')

    if header:
          for link in soup.find_all('a'):
              rewrite_relative_link_to_anchor(link)

          return {
                'status': status,
                'body': str(soup),
                'title': header.text,
                'ref': normalize_adr_ref(os.path.basename(path)),
            }
    else:
        return None


def rewrite_relative_link_to_anchor(link):
    href = link.attrs.get('href')
    if href:
        host = urlparse.urlparse(href).netloc
        if not host:
            # relative path
            link.attrs['href'] = '#' + normalize_adr_ref(link.attrs['href'])


def normalize_adr_ref(ref):
    """
    Transform a filename for use as an ID. Principally, remove "." since it interferes with jQuery
    """
    return os.path.splitext(ref)[0]


def render_html(config):

    env = Environment(
        loader=PackageLoader('adr_viewer', 'templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    template = env.get_template('index.html')

    return template.render(config=config)


def get_adr_files(path):
    files = glob.glob(path)
    files.sort()
    return files


def run_server(content):
    print('Starting server at http://localhost:8000/')
    app = Bottle()
    app.route('/', 'GET', lambda: content)
    run(app, host='localhost', port=8000, quiet=True)


def generate_content(path):

    files = get_adr_files("%s/*.md" % path)

    config = {
        'project_title': os.path.basename(os.getcwd()),
        'records': []
    }

    for index, adr_file in enumerate(files):

        adr_attributes = parse_adr_to_config(adr_file)

        if adr_attributes:
            adr_attributes['index'] = index

            config['records'].append(adr_attributes)
        else:
            print("Could not parse %s in ADR format, ignoring." % adr_file)

    return render_html(config)


@click.command()
@click.option('--adr-path', default='doc/adr/',   help='Directory containing ADR files.',         show_default=True)
@click.option('--output',   default='index.html', help='File to write output to.',                show_default=True)
@click.option('--serve',    default=False,        help='Serve content at http://localhost:8000/', is_flag=True)
def main(adr_path, output, serve):
    content = generate_content(adr_path)

    if serve:
        run_server(content)
    else:
        with open(output, 'w') as out:
            out.write(content)
